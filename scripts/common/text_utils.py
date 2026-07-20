"""Text and filename utility functions."""

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .constants import EM_TAG_RE, SAFE_CHAR_RE, SPACE_RE


def sanitize_filename(name: str, fallback: str = "unnamed") -> str:
    name = SAFE_CHAR_RE.sub("_", name).strip().rstrip(".")
    return name or fallback


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " | ".join(clean_text(item) for item in value if clean_text(item))
    text = str(value)
    text = EM_TAG_RE.sub("", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def decode_filename_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("response-content-disposition")
    if not values:
        return None
    disposition = values[0]
    match = re.search(r'filename="([^"]+)"', disposition, re.IGNORECASE)
    if not match:
        return None
    filename = match.group(1)
    try:
        filename = unquote(unquote(filename))
    except Exception:
        filename = unquote(filename)
    return sanitize_filename(filename)


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def format_request_exception(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    url = getattr(response, "url", "")
    status_code = getattr(response, "status_code", None)
    if url:
        redacted = redact_url(url)
        if status_code is not None:
            return f"{exc.__class__.__name__}: status={status_code} url={redacted}"
        return f"{exc.__class__.__name__}: url={redacted}"
    return str(exc)


def extract_year(value: str) -> str:
    match = re.search(r"(\d{4})", clean_text(value))
    return match.group(1) if match else "未知"


def create_crawler_headers(accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8") -> dict:
    from .constants import DEFAULT_USER_AGENT
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": accept,
    }
