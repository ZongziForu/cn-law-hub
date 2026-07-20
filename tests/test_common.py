#!/usr/bin/env python3
"""Unit tests for scripts/common/ratelimit.py and constants.py."""

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common.ratelimit import (
    SmartRateLimiter,
    RateLimitMode,
    http_request,
    _get_limiter,
    init_limiter,
)
from common.constants import VERIFY_SSL


class TestRateLimiterBasic(unittest.TestCase):
    def setUp(self):
        self.limiter = SmartRateLimiter()

    def test_off_mode_acquire_does_not_block(self):
        self.limiter.mode = RateLimitMode.OFF
        self.limiter.acquire()
        self.assertEqual(self.limiter._total_requests, 0)

    def test_fixed_mode_acquire_counts(self):
        self.limiter.mode = RateLimitMode.FIXED
        self.limiter._last_request_time = 0
        self.limiter._current_rps = 100  # very fast, won't block
        self.limiter.acquire()
        self.assertEqual(self.limiter._total_requests, 1)

    def test_report_429_increments_and_backs_off(self):
        self.limiter.mode = RateLimitMode.FIXED
        with mock.patch("time.sleep") as mock_sleep:
            self.limiter.report_429()
        self.assertEqual(self.limiter._429_count, 1)
        self.assertEqual(self.limiter._consecutive_429, 1)
        self.assertEqual(self.limiter._consecutive_success, 0)
        mock_sleep.assert_called_once()

    def test_report_429_adaptive_reduces_rps(self):
        self.limiter.mode = RateLimitMode.ADAPTIVE
        self.limiter._current_rps = 5.0
        with mock.patch("time.sleep"):
            self.limiter.report_429()
        self.assertLessEqual(self.limiter._current_rps, 3.0)

    def test_report_success_adaptive(self):
        self.limiter.mode = RateLimitMode.ADAPTIVE
        self.limiter._current_rps = 5.0
        self.limiter._consecutive_success = 4
        self.limiter.report_success(response_time_ms=300)
        # After 5 consecutive fast successes, speed up
        self.assertGreater(self.limiter._current_rps, 5.0)
        self.assertEqual(self.limiter._consecutive_429, 0)

    def test_print_summary_no_stderr_error(self):
        """Verify print_summary doesn't throw NameError for sys.stderr."""
        self.limiter.mode = RateLimitMode.FIXED
        self.limiter._total_requests = 5
        self.limiter._start_time = 0
        # Should not raise
        try:
            self.limiter.print_summary()
        except NameError:
            self.fail("print_summary raised NameError — missing sys import?")

    def test_report_429_no_stderr_error(self):
        """Verify report_429 doesn't throw NameError for sys.stderr or sys."""
        self.limiter.mode = RateLimitMode.FIXED
        with mock.patch("time.sleep"):
            try:
                self.limiter.report_429()
            except NameError:
                self.fail("report_429 raised NameError — missing sys import?")

    def test_mode_desc(self):
        self.limiter.mode = RateLimitMode.OFF
        self.assertIn("off", self.limiter.mode_desc())
        self.limiter.mode = RateLimitMode.FIXED
        self.assertIn("fixed", self.limiter.mode_desc())
        self.limiter.mode = RateLimitMode.ADAPTIVE
        self.assertIn("adaptive", self.limiter.mode_desc())

    def test_init_for_task_small(self):
        mode = self.limiter.init_for_task(5)
        self.assertEqual(mode, RateLimitMode.OFF)

    def test_init_for_task_large(self):
        mode = self.limiter.init_for_task(200)
        self.assertEqual(mode, RateLimitMode.ADAPTIVE)


class TestHttpRequestStatusCodes(unittest.TestCase):
    """Test http_request 4xx/5xx handling and session support."""

    def setUp(self):
        # Reset global limiter to OFF for predictable testing
        init_limiter("off")

    @mock.patch("requests.request")
    def test_200_returns_response(self, mock_req):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_req.return_value = mock_resp

        resp = http_request("GET", "https://example.com")
        self.assertEqual(resp.status_code, 200)

    @mock.patch("requests.request")
    def test_403_raises_runtime_error(self, mock_req):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 403
        mock_req.return_value = mock_resp

        with self.assertRaises(RuntimeError) as ctx:
            http_request("GET", "https://example.com/api/secret")
        self.assertIn("403", str(ctx.exception))
        self.assertIn("access denied", str(ctx.exception))

    @mock.patch("requests.request")
    def test_404_raises_runtime_error(self, mock_req):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        mock_req.return_value = mock_resp

        with self.assertRaises(RuntimeError) as ctx:
            http_request("GET", "https://example.com/notfound")
        self.assertIn("404", str(ctx.exception))
        self.assertIn("Not Found", str(ctx.exception))

    @mock.patch("requests.request")
    def test_429_retries_then_raises(self, mock_req):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 429
        mock_req.return_value = mock_resp

        with mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                http_request("GET", "https://example.com")
        self.assertIn("429", str(ctx.exception))

    @mock.patch("requests.request")
    def test_503_retries_then_raises(self, mock_req):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 503
        mock_req.return_value = mock_resp

        with mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                http_request("GET", "https://example.com")
        self.assertIn("503", str(ctx.exception))

    @mock.patch("requests.request")
    def test_400_client_error_no_retry(self, mock_req):
        """400 must raise immediately, never retry."""
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 400
        mock_req.return_value = mock_resp

        with self.assertRaises(RuntimeError) as ctx:
            http_request("GET", "https://example.com")
        self.assertIn("400", str(ctx.exception))
        self.assertIn("client error", str(ctx.exception))
        # Should only call once — no retry
        self.assertEqual(mock_req.call_count, 1)

    @mock.patch("requests.request")
    def test_allowed_statuses_returns_response(self, mock_req):
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 403
        mock_req.return_value = mock_resp

        resp = http_request(
            "GET", "https://example.com", allowed_statuses={403}
        )
        self.assertEqual(resp.status_code, 403)

    @mock.patch("requests.request")
    def test_url_redacted_in_error(self, mock_req):
        """Error messages must redact query params from URLs."""
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 403
        mock_req.return_value = mock_resp

        with self.assertRaises(RuntimeError) as ctx:
            http_request("GET", "https://example.com/api?token=secret&key=abc")
        msg = str(ctx.exception)
        self.assertNotIn("token=secret", msg)
        self.assertIn("example.com/api", msg)


class TestHttpRequestSession(unittest.TestCase):
    """Test http_request with session parameter preserves cookies."""

    def setUp(self):
        init_limiter("off")

    def test_session_passed_to_request(self):
        """When session is provided, use session.request not requests.request."""
        import requests as req_mod

        session = mock.MagicMock(spec=req_mod.Session)
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        session.request.return_value = mock_resp

        with mock.patch("requests.request") as mock_global:
            resp = http_request(
                "GET", "https://example.com", session=session
            )
        self.assertEqual(resp.status_code, 200)
        session.request.assert_called_once()
        mock_global.assert_not_called()

    def test_session_cookies_preserved(self):
        """Session object remains unchanged after request — caller can read cookies."""
        import requests as req_mod

        session = req_mod.Session()
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200

        with mock.patch.object(session, "request", return_value=mock_resp):
            resp = http_request(
                "GET", "https://example.com", session=session
            )
        # Session object identity preserved
        self.assertIsInstance(session, req_mod.Session)
        self.assertEqual(resp.status_code, 200)


class TestVerifySSLDefault(unittest.TestCase):
    def test_verify_ssl_defaults_true(self):
        """VERIFY_SSL should default to True (secure by default)."""
        self.assertTrue(VERIFY_SSL)

    def test_verify_ssl_respects_env(self):
        """Explicit CN_LAW_VERIFY_SSL=0 should disable verification."""
        with mock.patch.dict("os.environ", {"CN_LAW_VERIFY_SSL": "0"}, clear=True):
            # Re-import to get fresh value
            import importlib
            from scripts.common import constants
            importlib.reload(constants)
            self.assertFalse(constants.VERIFY_SSL)
            # Restore
            importlib.reload(constants)

    def test_npc_verify_ssl_backward_compat(self):
        """NPC_LAW_VERIFY_SSL should still work as fallback."""
        with mock.patch.dict("os.environ", {"NPC_LAW_VERIFY_SSL": "0"}, clear=True):
            import importlib
            from scripts.common import constants
            importlib.reload(constants)
            self.assertFalse(constants.VERIFY_SSL)
            # Restore
            importlib.reload(constants)


if __name__ == "__main__":
    unittest.main()
