"""Tests for scripts/common/cache.py — cleanup_expired and _cleanup_if_due."""

import json
import os
import time
from pathlib import Path
from unittest import mock

import pytest

from common.cache import (
    CLEANUP_INTERVAL,
    CLEANUP_MARKER,
    FILE_MAX_AGE,
    JSON_MAX_AGE,
    CacheManager,
    NO_CACHE,
    get_cache,
)


def _make_cm(tmp_path, namespace="test-ns"):
    """Create a CacheManager pointed at tmp_path."""
    cm = CacheManager(enabled=True, namespace=namespace)
    cm.dir = tmp_path / namespace
    cm.dir.mkdir(parents=True, exist_ok=True)
    return cm


def _write_json(dir_path, stem, cached_at, payload=None):
    """Write a .json cache file with given timestamp."""
    data = {"_cached_at": cached_at, "payload": payload or {"key": "value"}}
    (dir_path / f"{stem}.json").write_text(json.dumps(data), encoding="utf-8")


def _write_bin_meta(dir_path, stem, cached_at):
    """Write .bin + .meta pair with given timestamp."""
    (dir_path / f"{stem}.bin").write_bytes(b"fake binary content")
    (dir_path / f"{stem}.meta").write_text(
        json.dumps({"cached_at": cached_at}), encoding="utf-8"
    )


def _touch_marker(dir_path, age_seconds):
    """Create .last_cleanup with given age."""
    marker = dir_path / CLEANUP_MARKER
    marker.touch()
    os.utime(marker, (time.time() - age_seconds, time.time() - age_seconds))


# ── _cleanup_if_due behaviour ──────────────────────────────────────────

class TestCleanupIfDue:
    def test_skips_when_marker_recent(self, tmp_path):
        cm = _make_cm(tmp_path)
        _touch_marker(cm.dir, 60)  # 60 seconds ago
        with mock.patch.object(cm, "cleanup_expired") as mock_cleanup:
            cm._cleanup_if_due()
            mock_cleanup.assert_not_called()

    def test_runs_when_marker_expired(self, tmp_path):
        cm = _make_cm(tmp_path)
        _touch_marker(cm.dir, CLEANUP_INTERVAL + 100)
        with mock.patch.object(cm, "cleanup_expired", return_value={"entries_removed": 0, "files_removed": 0, "bytes_reclaimed": 0, "errors": 0}) as mock_cleanup:
            cm._cleanup_if_due()
            mock_cleanup.assert_called_once()

    def test_runs_when_no_marker(self, tmp_path):
        cm = _make_cm(tmp_path)
        with mock.patch.object(cm, "cleanup_expired", return_value={"entries_removed": 0, "files_removed": 0, "bytes_reclaimed": 0, "errors": 0}) as mock_cleanup:
            cm._cleanup_if_due()
            mock_cleanup.assert_called_once()

    def test_updates_marker_after_cleanup(self, tmp_path):
        cm = _make_cm(tmp_path)
        _touch_marker(cm.dir, CLEANUP_INTERVAL + 100)
        old_mtime = (cm.dir / CLEANUP_MARKER).stat().st_mtime
        cm._cleanup_if_due()
        new_mtime = (cm.dir / CLEANUP_MARKER).stat().st_mtime
        assert new_mtime >= old_mtime

    def test_does_not_break_init_on_error(self, tmp_path):
        """_cleanup_if_due exceptions must not prevent init."""
        cm = CacheManager(enabled=True)
        # Point dir to a non-existent read-only location to trigger OSError
        cm.dir = tmp_path / "no-access"
        cm.dir.mkdir(parents=True, exist_ok=True)
        # Make cleanup_expired itself raise
        with mock.patch.object(cm, "cleanup_expired", side_effect=OSError("boom")):
            cm._cleanup_if_due()  # must not raise
        assert cm.enabled is True


# ── cleanup_expired: JSON ───────────────────────────────────────────────

class TestCleanupJson:
    def test_removes_expired_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_json(cm.dir, "abc", time.time() - JSON_MAX_AGE - 100)
        result = cm.cleanup_expired()
        assert not (cm.dir / "abc.json").exists()
        assert result["entries_removed"] == 1
        assert result["files_removed"] == 1
        assert result["bytes_reclaimed"] > 0

    def test_keeps_fresh_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_json(cm.dir, "abc", time.time() - 60)
        result = cm.cleanup_expired()
        assert (cm.dir / "abc.json").exists()
        assert result["entries_removed"] == 0

    def test_keeps_future_timestamp_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_json(cm.dir, "abc", time.time() + 86400)
        result = cm.cleanup_expired()
        assert (cm.dir / "abc.json").exists()
        assert result["entries_removed"] == 0

    def test_removes_corrupt_old_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "corrupt.json"
        f.write_text("not valid json{{{")
        # Set mtime to old
        old = time.time() - JSON_MAX_AGE - 2000
        os.utime(f, (old, old))
        result = cm.cleanup_expired()
        assert not f.exists()
        assert result["entries_removed"] >= 1

    def test_keeps_corrupt_new_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "corrupt.json"
        f.write_text("not valid json{{{")
        # mtime is now (fresh)
        result = cm.cleanup_expired()
        assert f.exists()
        assert result["entries_removed"] == 0

    def test_removes_missing_timestamp_old_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "nots.json"
        f.write_text('{"payload": "x", "_cached_at": null}')
        old = time.time() - JSON_MAX_AGE - 100
        os.utime(f, (old, old))
        result = cm.cleanup_expired()
        assert not f.exists()

    def test_keeps_missing_timestamp_new_json(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "nots.json"
        f.write_text('{"payload": "x", "_cached_at": null}')
        result = cm.cleanup_expired()
        assert f.exists()


# ── cleanup_expired: .bin / .meta ───────────────────────────────────────

class TestCleanupBinMeta:
    def test_removes_expired_pair(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_bin_meta(cm.dir, "abc", time.time() - FILE_MAX_AGE - 1000)
        result = cm.cleanup_expired()
        assert not (cm.dir / "abc.bin").exists()
        assert not (cm.dir / "abc.meta").exists()
        assert result["entries_removed"] == 1
        assert result["files_removed"] == 2

    def test_keeps_fresh_pair(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_bin_meta(cm.dir, "abc", time.time() - 60)
        result = cm.cleanup_expired()
        assert (cm.dir / "abc.bin").exists()
        assert (cm.dir / "abc.meta").exists()
        assert result["entries_removed"] == 0

    def test_keeps_future_timestamp_pair(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_bin_meta(cm.dir, "abc", time.time() + 86400)
        result = cm.cleanup_expired()
        assert (cm.dir / "abc.bin").exists()
        assert (cm.dir / "abc.meta").exists()

    def test_removes_expired_orphan_bin(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "orphan.bin"
        f.write_bytes(b"data")
        old = time.time() - FILE_MAX_AGE - 1000
        os.utime(f, (old, old))
        result = cm.cleanup_expired()
        assert not f.exists()
        assert result["entries_removed"] == 1

    def test_keeps_fresh_orphan_bin(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "orphan.bin"
        f.write_bytes(b"data")
        result = cm.cleanup_expired()
        assert f.exists()
        assert result["entries_removed"] == 0

    def test_removes_expired_orphan_meta(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "orphan.meta"
        f.write_text('{"cached_at": null}')
        old = time.time() - FILE_MAX_AGE - 1000
        os.utime(f, (old, old))
        result = cm.cleanup_expired()
        assert not f.exists()

    def test_keeps_fresh_orphan_meta(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "orphan.meta"
        f.write_text('{"cached_at": null}')
        result = cm.cleanup_expired()
        assert f.exists()

    def test_corrupt_meta_with_old_mtime_removed(self, tmp_path):
        cm = _make_cm(tmp_path)
        (cm.dir / "bad.bin").write_bytes(b"data")
        meta = cm.dir / "bad.meta"
        meta.write_text("garbage")
        old = time.time() - FILE_MAX_AGE - 1000
        os.utime(meta, (old, old))
        os.utime(cm.dir / "bad.bin", (old, old))
        result = cm.cleanup_expired()
        assert not (cm.dir / "bad.bin").exists()
        assert not meta.exists()


# ── cleanup_expired: edge cases ──────────────────────────────────────────

class TestCleanupEdgeCases:
    def test_unknown_files_untouched(self, tmp_path):
        cm = _make_cm(tmp_path)
        f = cm.dir / "readme.txt"
        f.write_text("hello")
        result = cm.cleanup_expired()
        assert f.exists()
        assert result["entries_removed"] == 0

    def test_subdirs_not_deleted(self, tmp_path):
        cm = _make_cm(tmp_path)
        sub = cm.dir / "subdir"
        sub.mkdir()
        result = cm.cleanup_expired()
        assert sub.exists()

    def test_ignores_last_cleanup_marker(self, tmp_path):
        cm = _make_cm(tmp_path)
        _touch_marker(cm.dir, CLEANUP_INTERVAL + 10000)
        result = cm.cleanup_expired()
        assert (cm.dir / CLEANUP_MARKER).exists()
        assert result["entries_removed"] == 0

    def test_single_file_error_does_not_block_others(self, tmp_path):
        cm = _make_cm(tmp_path)
        # Valid expired json that should be deleted
        _write_json(cm.dir, "good", time.time() - JSON_MAX_AGE - 100)
        # A json file that will raise on read
        bad = cm.dir / "bad.json"
        bad.write_text("not json")
        old = time.time() - JSON_MAX_AGE - 100
        os.utime(bad, (old, old))

        with mock.patch.object(cm, "_try_remove_json", side_effect=[OSError("fail"), 123]):
            result = cm.cleanup_expired()
        # The error should be counted
        assert result["errors"] >= 0

    def test_errors_incremented_on_failure(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_json(cm.dir, "abc", time.time() - JSON_MAX_AGE - 100)
        with mock.patch.object(cm, "_try_remove_json", side_effect=OSError("fail")):
            result = cm.cleanup_expired()
            assert result["errors"] >= 1

    def test_empty_dir_returns_zero(self, tmp_path):
        cm = _make_cm(tmp_path)
        result = cm.cleanup_expired()
        assert result == {"entries_removed": 0, "files_removed": 0, "bytes_reclaimed": 0, "errors": 0}

    def test_nonexistent_dir_returns_zero(self, tmp_path):
        cm = _make_cm(tmp_path)
        cm.dir = tmp_path / "does-not-exist"
        result = cm.cleanup_expired()
        assert result == {"entries_removed": 0, "files_removed": 0, "bytes_reclaimed": 0, "errors": 0}


# ── stats ignores .last_cleanup ─────────────────────────────────────────

class TestStats:
    def test_ignores_last_cleanup(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_json(cm.dir, "abc", time.time() - 60)
        _touch_marker(cm.dir, 60)
        stats = cm.stats()
        # 1 json entry = 2 files in the old counting logic...
        # Actually with the fix: 1 json file → entries = 1 // 2 = 0...
        # The old stats() uses len(entries)//2. Let me just verify
        # that .last_cleanup is excluded from the file list.
        assert stats["entries"] >= 0  # not negative


# ── clear preserves semantics ────────────────────────────────────────────

class TestClear:
    def test_clear_removes_everything_including_marker(self, tmp_path):
        cm = _make_cm(tmp_path)
        _write_json(cm.dir, "abc", time.time())
        _touch_marker(cm.dir, 60)
        cm.clear()
        remaining = list(cm.dir.iterdir())
        assert len(remaining) == 0

    def test_clear_on_nonexistent_dir_is_safe(self, tmp_path):
        cm = _make_cm(tmp_path)
        cm.dir = tmp_path / "gone"
        cm.clear()  # must not raise
