"""File-based cache with TTL support."""

import hashlib
import json
import time
from pathlib import Path

from .constants import NO_CACHE


class CacheManager:
    """File-based cache with TTL support."""

    def __init__(self, enabled: bool = True, namespace: str = "npc-law-db"):
        self.enabled = enabled and not NO_CACHE
        self.dir = Path.home() / ".cache" / namespace
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

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
        entries = list(self.dir.iterdir())
        total_size = sum(f.stat().st_size for f in entries if f.is_file())
        return {"entries": len(entries) // 2, "size_kb": round(total_size / 1024, 1)}


_cache: CacheManager | None = None


def get_cache(namespace: str = "npc-law-db") -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    if namespace == "npc-law-db":
        return _cache
    return CacheManager(namespace=namespace)
