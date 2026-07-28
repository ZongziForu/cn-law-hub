"""File-based cache with TTL support."""

import hashlib
import json
import os
import time
from pathlib import Path

from .constants import NO_CACHE

# Maximum on-disk retention per file type
JSON_MAX_AGE = 86400        # .json cache entries: 24h
FILE_MAX_AGE = 604800       # .bin/.meta binary cache: 7 days
CLEANUP_INTERVAL = 604800   # cleanup throttle: 7 days
CLEANUP_MARKER = ".last_cleanup"


class CacheManager:
    """File-based cache with TTL support."""

    def __init__(self, enabled: bool = True, namespace: str = "npc-law-db"):
        self.enabled = enabled and not NO_CACHE
        self.dir = Path.home() / ".cache" / namespace
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_if_due()

    def _key(self, *parts: str) -> str:
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _path(self, key: str, suffix: str = ".json") -> Path:
        return self.dir / f"{key}{suffix}"

    def get(self, key: str, max_age: float = 3600):
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("_cached_at", 0) > max_age:
                return None
            return data.get("payload")
        except Exception:
            return None

    def set(self, key: str, payload: dict) -> None:
        if not self.enabled:
            return
        try:
            self._path(key).write_text(
                json.dumps({"_cached_at": time.time(), "payload": payload}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get_file(self, key: str, max_age: float = 604800) -> bytes | None:
        if not self.enabled:
            return None
        path = self._path(key, ".bin")
        meta_path = self._path(key, ".meta")
        if not path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if time.time() - meta.get("cached_at", 0) > max_age:
                return None
            return path.read_bytes()
        except Exception:
            return None

    def set_file(self, key: str, data: bytes) -> None:
        if not self.enabled:
            return
        try:
            self._path(key, ".bin").write_bytes(data)
            self._path(key, ".meta").write_text(
                json.dumps({"cached_at": time.time()}), encoding="utf-8"
            )
        except Exception:
            pass

    def clear(self) -> None:
        import shutil
        if self.dir.exists():
            shutil.rmtree(self.dir)
            self.dir.mkdir(parents=True, exist_ok=True)

    def stats(self) -> dict:
        if not self.dir.exists():
            return {"entries": 0, "size_kb": 0}
        entries = [f for f in self.dir.iterdir() if f.name != CLEANUP_MARKER]
        total_size = sum(f.stat().st_size for f in entries if f.is_file())
        return {"entries": len(entries) // 2, "size_kb": round(total_size / 1024, 1)}

    # ---- Cache cleanup ----

    def _cleanup_if_due(self) -> None:
        """Conditionally run cleanup if last cleanup was > CLEANUP_INTERVAL ago."""
        try:
            marker = self.dir / CLEANUP_MARKER
            if marker.exists():
                try:
                    last = marker.stat().st_mtime
                    if time.time() - last < CLEANUP_INTERVAL:
                        return
                except OSError:
                    pass  # stat failed → run cleanup anyway
            self.cleanup_expired()
            try:
                marker.touch()
            except OSError:
                pass
        except OSError:
            pass  # never let maintenance break init

    def cleanup_expired(self, now: float | None = None) -> dict:
        """Delete expired cache files from this namespace.

        .json files older than JSON_MAX_AGE and .bin/.meta pairs older than
        FILE_MAX_AGE are removed.  Returns a summary dict.
        """
        if now is None:
            now = time.time()

        result = {
            "entries_removed": 0,
            "files_removed": 0,
            "bytes_reclaimed": 0,
            "errors": 0,
        }

        if not self.dir.exists():
            return result

        # Collect files by stem
        json_files = []
        bin_files = {}   # stem -> Path
        meta_files = {}  # stem -> Path

        for entry in self.dir.iterdir():
            if not entry.is_file() or entry.name == CLEANUP_MARKER:
                continue
            stem = entry.stem
            suffix = entry.suffix
            if suffix == ".json":
                json_files.append(entry)
            elif suffix == ".bin":
                bin_files[stem] = entry
            elif suffix == ".meta":
                meta_files[stem] = entry
            # Unknown files are ignored

        # --- Clean .json files ---
        for f in json_files:
            try:
                removed = self._try_remove_json(f, now)
            except OSError:
                result["errors"] += 1
                continue
            if removed:
                result["entries_removed"] += 1
                result["files_removed"] += 1
                result["bytes_reclaimed"] += removed

        # --- Clean .bin/.meta pairs ---
        all_stems = set(bin_files.keys()) | set(meta_files.keys())
        for stem in all_stems:
            try:
                removed = self._try_remove_bin_meta(
                    stem, bin_files.get(stem), meta_files.get(stem), now
                )
            except OSError:
                result["errors"] += 1
                continue
            if removed:
                result["entries_removed"] += 1
                result["files_removed"] += removed["files"]
                result["bytes_reclaimed"] += removed["bytes"]

        return result

    def _try_remove_json(self, path: Path, now: float) -> int:
        """Try to remove an expired .json file.  Returns bytes reclaimed, or 0."""
        size = path.stat().st_size
        expired = False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = data.get("_cached_at")
            if isinstance(ts, (int, float)) and ts > 0:
                if ts > now:
                    return 0  # future timestamp, keep
                if now - ts > JSON_MAX_AGE:
                    expired = True
            else:
                # Corrupt or missing timestamp → fall back to mtime
                if now - path.stat().st_mtime > JSON_MAX_AGE:
                    expired = True
        except (json.JSONDecodeError, ValueError):
            # Unreadable JSON → fall back to mtime
            try:
                if now - path.stat().st_mtime > JSON_MAX_AGE:
                    expired = True
            except OSError:
                return 0

        if expired:
            path.unlink(missing_ok=True)
            return size
        return 0

    def _try_remove_bin_meta(
        self, stem: str, bin_path: Path | None, meta_path: Path | None, now: float
    ) -> dict | None:
        """Try to remove expired .bin/.meta pair or orphan. Returns {files, bytes} or None."""
        has_bin = bin_path is not None
        has_meta = meta_path is not None

        if not has_bin and not has_meta:
            return None

        expired = self._bin_meta_expired(stem, bin_path, meta_path, now, has_bin, has_meta)
        if not expired:
            return None

        files = 0
        bytes_reclaimed = 0
        if bin_path:
            try:
                bytes_reclaimed += bin_path.stat().st_size
            except OSError:
                pass
            try:
                bin_path.unlink(missing_ok=True)
                files += 1
            except OSError:
                pass
        if meta_path:
            try:
                bytes_reclaimed += meta_path.stat().st_size
            except OSError:
                pass
            try:
                meta_path.unlink(missing_ok=True)
                files += 1
            except OSError:
                pass
        return {"files": files, "bytes": bytes_reclaimed}

    def _bin_meta_expired(
        self, stem: str, bin_path: Path | None, meta_path: Path | None, now: float,
        has_bin: bool, has_meta: bool
    ) -> bool:
        """Determine whether a .bin/.meta entry is expired."""
        ts = None

        if has_meta:
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                ts = data.get("cached_at")
            except (json.JSONDecodeError, ValueError, OSError):
                pass

        if isinstance(ts, (int, float)) and ts > 0:
            if ts > now:
                return False  # future
            if now - ts > FILE_MAX_AGE:
                return True
            return False

        # No valid timestamp → fall back to mtime
        mtimes = []
        try:
            if bin_path:
                mtimes.append(bin_path.stat().st_mtime)
        except OSError:
            pass
        try:
            if meta_path:
                mtimes.append(meta_path.stat().st_mtime)
        except OSError:
            pass

        if not mtimes:
            return False

        # Both files (or the sole file) must be older than FILE_MAX_AGE
        return all(now - mt > FILE_MAX_AGE for mt in mtimes)


_cache: CacheManager | None = None


def get_cache(namespace: str = "npc-law-db") -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    if namespace == "npc-law-db":
        return _cache
    return CacheManager(namespace=namespace)
