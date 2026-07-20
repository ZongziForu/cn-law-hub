"""Smart rate limiter and HTTP client with retry/429 handling."""

import random
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .constants import BASE_BACKOFF, MAX_BACKOFF, MAX_RETRIES, RETRYABLE_STATUS_CODES, VERIFY_SSL
from .text_utils import format_request_exception


class RateLimitMode(Enum):
    AUTO = auto()
    OFF = auto()
    FIXED = auto()
    ADAPTIVE = auto()


@dataclass
class RateLimitConfig:
    fixed_rps: float = 5.0
    adaptive_initial_rps: float = 5.0
    adaptive_min_rps: float = 1.0
    adaptive_max_rps: float = 8.0
    small_task_threshold: int = 10
    large_task_threshold: int = 100
    backoff_on_429: float = 2.0


class SmartRateLimiter:
    """Task-size-aware rate limiter: no throttle for small tasks, auto-throttle for large."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.cfg = config or RateLimitConfig()
        self.mode: RateLimitMode = RateLimitMode.OFF
        self._current_rps: float = self.cfg.adaptive_initial_rps
        self._consecutive_success: int = 0
        self._consecutive_429: int = 0
        self._last_request_time: float = 0
        self._total_requests: int = 0
        self._limited_requests: int = 0
        self._start_time: Optional[float] = None
        self._429_count: int = 0

    @staticmethod
    def estimate_task_size(**kwargs) -> int:
        total = 0
        if kwargs.get("search"):
            pages = max(1, (kwargs.get("size", 20) + 99) // 100)
            total += pages
            if kwargs.get("urls_only"):
                avg_per_page = min(100, kwargs.get("size", 20))
                total += pages * avg_per_page
        if "download_list" in kwargs:
            total += len(kwargs["download_list"])
        if "info_list" in kwargs:
            total += len(kwargs["info_list"])
        if "preview_list" in kwargs:
            total += len(kwargs["preview_list"])
        if "article_count" in kwargs:
            total += kwargs["article_count"]
        if kwargs.get("info"):
            total += 1
        if kwargs.get("download"):
            total += 1
        if kwargs.get("preview"):
            total += 1
        if kwargs.get("article"):
            total += 1
        return max(1, total)

    def init_for_task(self, estimated_requests: int,
                      forced_mode: Optional[RateLimitMode] = None) -> RateLimitMode:
        if forced_mode:
            self.mode = forced_mode
        else:
            if estimated_requests <= self.cfg.small_task_threshold:
                self.mode = RateLimitMode.OFF
            elif estimated_requests <= self.cfg.large_task_threshold:
                self.mode = RateLimitMode.FIXED
            else:
                self.mode = RateLimitMode.ADAPTIVE
        self._current_rps = self.cfg.adaptive_initial_rps
        self._consecutive_success = 0
        self._consecutive_429 = 0
        self._last_request_time = 0
        self._total_requests = 0
        self._limited_requests = 0
        self._start_time = time.time()
        self._429_count = 0
        return self.mode

    def mode_desc(self) -> str:
        return {
            RateLimitMode.OFF: "off (small task)",
            RateLimitMode.FIXED: f"fixed {self.cfg.fixed_rps:.0f} req/s",
            RateLimitMode.ADAPTIVE: f"adaptive ({self._current_rps:.1f} req/s)",
            RateLimitMode.AUTO: "auto",
        }.get(self.mode, "unknown")

    def acquire(self):
        if self.mode == RateLimitMode.OFF:
            return
        self._total_requests += 1
        interval = 1.0 / (self._current_rps if self.mode == RateLimitMode.ADAPTIVE
                          else self.cfg.fixed_rps)
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < interval:
            time.sleep(interval - elapsed)
            self._limited_requests += 1
        self._last_request_time = time.time()

    def report_success(self, response_time_ms: float = 0):
        if self.mode != RateLimitMode.ADAPTIVE:
            return
        self._consecutive_success += 1
        self._consecutive_429 = 0
        if self._consecutive_success >= 5 and response_time_ms < 500:
            self._current_rps = min(self._current_rps * 1.1, self.cfg.adaptive_max_rps)
            self._consecutive_success = 0

    def report_429(self):
        self._429_count += 1
        self._consecutive_success = 0
        self._consecutive_429 += 1
        exp = min(BASE_BACKOFF * (2 ** (self._consecutive_429 - 1)), MAX_BACKOFF)
        jitter = random.uniform(0, exp * 0.3)
        backoff = max(0.1, exp + jitter)
        print(f"  [429] Rate limited. Backing off {backoff:.1f}s..."
              f" (strike {self._consecutive_429})", file=sys.stderr)
        time.sleep(backoff)
        if self.mode == RateLimitMode.ADAPTIVE:
            self._current_rps = max(self._current_rps * 0.6, self.cfg.adaptive_min_rps)
            print(f"  [Adaptive] Reduced to {self._current_rps:.1f} req/s", file=sys.stderr)

    def report_slow(self, response_time_ms: float):
        if self.mode == RateLimitMode.ADAPTIVE and response_time_ms > 2000:
            self._current_rps = max(self._current_rps * 0.85, self.cfg.adaptive_min_rps)

    def print_summary(self):
        if self._total_requests == 0:
            return
        elapsed = time.time() - (self._start_time or time.time())
        actual_rps = self._total_requests / elapsed if elapsed > 0 else 0
        r429 = f" | 429s: {self._429_count}" if self._429_count else ""
        print(f"\n[RateLimit] {self.mode_desc()} | "
              f"{self._total_requests} requests in {elapsed:.1f}s "
              f"({actual_rps:.1f} req/s){r429}",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# Global limiter + HTTP request helper
# ---------------------------------------------------------------------------

_limiter: Optional[SmartRateLimiter] = None


def _get_limiter() -> SmartRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SmartRateLimiter()
    return _limiter


def init_limiter(mode_str: str = "auto", **kwargs):
    global _limiter
    config = RateLimitConfig(**kwargs) if kwargs else None
    _limiter = SmartRateLimiter(config)
    mode_map = {
        "off": RateLimitMode.OFF,
        "fixed": RateLimitMode.FIXED,
        "adaptive": RateLimitMode.ADAPTIVE,
        "auto": RateLimitMode.AUTO,
    }
    forced = None
    if mode_str in mode_map and mode_map[mode_str] != RateLimitMode.AUTO:
        forced = mode_map[mode_str]
    return _limiter, forced


def _backoff(attempt: int) -> float:
    exp = min(BASE_BACKOFF * (2 ** (attempt - 1)), MAX_BACKOFF)
    jitter = random.uniform(0, exp * 0.3)
    return max(0.1, exp + jitter)


def http_request(method, url, headers=None, **kwargs):
    """Make an HTTP request with rate limiting, 429 handling, and retries."""
    kwargs.setdefault("timeout", kwargs.pop("timeout", 30))
    kwargs.setdefault("verify", VERIFY_SSL)

    limiter = _get_limiter()
    limiter.acquire()

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            resp = requests.request(method, url, headers=headers, **kwargs)
            elapsed_ms = (time.time() - start) * 1000

            if resp.status_code == 429:
                limiter.report_429()
                last_err = "HTTP 429"
                if attempt < MAX_RETRIES:
                    continue
                raise RuntimeError(f"HTTP 429 Too Many Requests after {MAX_RETRIES} retries")

            if resp.status_code in RETRYABLE_STATUS_CODES:
                last_err = f"HTTP {resp.status_code}"
                if attempt < MAX_RETRIES:
                    time.sleep(_backoff(attempt))
                    continue
                raise RuntimeError(f"HTTP {resp.status_code} after {MAX_RETRIES} retries")

            limiter.report_success(elapsed_ms)

            if elapsed_ms > 2000:
                limiter.report_slow(elapsed_ms)

            if resp.status_code < 500:
                return resp

            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            last_err = format_request_exception(e)

        if attempt < MAX_RETRIES:
            time.sleep(_backoff(attempt))

    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {last_err}")
