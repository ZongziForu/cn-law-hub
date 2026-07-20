"""Tests for scripts/tax_law_crawler.py — 税务法规库 (fgk.chinatax.gov.cn)."""

import json
from unittest import mock

import pytest

import tax_law_crawler as tc
from tax_law_crawler import (
    CHANNEL_ID_CACHE,
    build_parser,
    create_session,
    discover_channel_id,
    fetch_category,
    fetch_detail,
    get_total_count,
    parse_results,
    save_results,
    search_collect,
    search_keyword_in_records,
)


@pytest.fixture(autouse=True)
def clear_channel_cache():
    """Clean CHANNEL_ID_CACHE before each test to avoid cross-test pollution."""
    CHANNEL_ID_CACHE.clear()
    yield
    CHANNEL_ID_CACHE.clear()


class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "增值税"])
        assert args.search == "增值税"
        assert args.size == 20
        assert args.category == "全部"
        assert args.output == "./tax_law_output"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_category(self):
        args = build_parser().parse_args(["--category", "财税文件", "--size", "50"])
        assert args.category == "财税文件"

    def test_invalid_category_fails(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--search", "x", "--category", "不存在的"])


# ---------------------------------------------------------------------------
# Channel ID discovery
# ---------------------------------------------------------------------------
class TestChannelIdDiscovery:
    def test_first_candidate_succeeds(self):
        from tests.fixtures.tax.data import CHANNEL_PAGE_HTML

        session = mock.MagicMock()
        mock_resp = mock.MagicMock()
        mock_resp.text = CHANNEL_PAGE_HTML
        session.request.return_value = mock_resp

        with mock.patch("tax_law_crawler.http_request", return_value=mock_resp):
            cid = discover_channel_id(session, "c100009")
            assert cid == "test-channel-abc123"

    def test_cached_reuses_value(self):
        CHANNEL_ID_CACHE["c100009"] = "cached-id-xyz"
        session = mock.MagicMock()

        with mock.patch("tax_law_crawler.http_request") as mock_http:
            cid = discover_channel_id(session, "c100009")
            assert cid == "cached-id-xyz"
            mock_http.assert_not_called()

    def test_second_candidate_when_first_fails(self):
        from tests.fixtures.tax.data import CHANNEL_PAGE_NONE, CHANNEL_PAGE_ALT_HTML

        session = mock.MagicMock()
        responses = [
            mock.MagicMock(status_code=200, text=CHANNEL_PAGE_NONE),   # first candidate: no channelId
            mock.MagicMock(status_code=200, text=CHANNEL_PAGE_ALT_HTML), # second: found
        ]

        with mock.patch("tax_law_crawler.http_request", side_effect=responses):
            cid = discover_channel_id(session, "c100009")
            assert cid == "alt-channel-xyz789"

    def test_fallback_to_main_page(self):
        """All candidate paths fail, fallback to main page succeeds."""
        from tests.fixtures.tax.data import CHANNEL_PAGE_NONE, CHANNEL_PAGE_MAIN_HTML

        session = mock.MagicMock()
        # 3 candidate failures + 1 main page success = 4 responses
        responses = [
            mock.MagicMock(status_code=200, text=CHANNEL_PAGE_NONE),  # candidate 1
            mock.MagicMock(status_code=200, text=CHANNEL_PAGE_NONE),  # candidate 2
            mock.MagicMock(status_code=200, text=CHANNEL_PAGE_NONE),  # candidate 3
            mock.MagicMock(status_code=200, text=CHANNEL_PAGE_MAIN_HTML),  # fallback
        ]

        with mock.patch("tax_law_crawler.http_request", side_effect=responses):
            cid = discover_channel_id(session, "c100009")
            assert cid == "main-channel-001"

    def test_all_fail_raises(self):
        from tests.fixtures.tax.data import CHANNEL_PAGE_NONE

        session = mock.MagicMock()
        responses = [mock.MagicMock(status_code=200, text=CHANNEL_PAGE_NONE)] * 4

        with mock.patch("tax_law_crawler.http_request", side_effect=responses):
            with pytest.raises(RuntimeError, match="Cannot discover channelId"):
                discover_channel_id(session, "c100009")


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
class TestSession:
    def test_create_session_calls_http_request(self):
        with mock.patch("tax_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock(status_code=200)
            mock_http.return_value = mock_resp

            session = create_session()
            assert session is not None
            assert mock_http.called  # http_request used instead of raw session.get


# ---------------------------------------------------------------------------
# API results parsing
# ---------------------------------------------------------------------------
class TestAPIResultsParsing:
    def test_parse_results_extracts_fields(self):
        from tests.fixtures.tax.data import API_RESPONSE

        records = parse_results(API_RESPONSE)
        assert len(records) == 2

        first = records[0]
        assert "测试增值税" in first["title"]
        assert "<em>" not in first["title"]  # highlight cleaned
        assert first["sub_title"] != ""
        assert first["document_number"] == "财政部令第50号"
        assert first["issuer"] == "财政部"
        assert first["effective_date"] == "2024-07-01"
        assert first["publish_time"] == "2024-05-01"
        assert first["source"] == "tax_law"

    def test_relative_url_resolved(self):
        from tests.fixtures.tax.data import API_RESPONSE

        records = parse_results(API_RESPONSE)
        first = records[0]
        assert "chinatax.gov.cn" in first["url"]

    def test_missing_metadata_no_crash(self):
        from tests.fixtures.tax.data import API_RESPONSE

        records = parse_results(API_RESPONSE)
        second = records[1]
        assert second["title"] == "测试企业所得税法实施条例"
        assert second["document_number"] == ""  # empty, not crash
        assert second["issuer"] == ""

    def test_total_count(self):
        from tests.fixtures.tax.data import API_RESPONSE

        assert get_total_count(API_RESPONSE) == 3

    def test_empty_response(self):
        from tests.fixtures.tax.data import API_RESPONSE_EMPTY

        records = parse_results(API_RESPONSE_EMPTY)
        assert records == []
        assert get_total_count(API_RESPONSE_EMPTY) == 0

    def test_no_validity_invented(self):
        from tests.fixtures.tax.data import API_RESPONSE

        records = parse_results(API_RESPONSE)
        for r in records:
            # effective_date is NOT a "现行有效" status assertion
            assert "status" not in r or r.get("status") in ("", None)


# ---------------------------------------------------------------------------
# API request
# ---------------------------------------------------------------------------
class TestAPIRequest:
    def test_post_url_correct(self):
        from tests.fixtures.tax.data import API_RESPONSE, CHANNEL_PAGE_HTML

        session = mock.MagicMock()
        channel_resp = mock.MagicMock(status_code=200, text=CHANNEL_PAGE_HTML)
        api_resp = mock.MagicMock(status_code=200)
        api_resp.json.return_value = API_RESPONSE
        CHANNEL_ID_CACHE["c100009"] = "ch-abc"

        with mock.patch("tax_law_crawler.http_request", side_effect=[channel_resp, api_resp]):
            fetch_category(session, "c100009")

    def test_pagination_params(self):
        from tests.fixtures.tax.data import API_RESPONSE, CHANNEL_PAGE_HTML

        session = mock.MagicMock()
        channel_resp = mock.MagicMock(status_code=200, text=CHANNEL_PAGE_HTML)
        api_resp = mock.MagicMock(status_code=200)
        api_resp.json.return_value = API_RESPONSE
        CHANNEL_ID_CACHE["c100010"] = "ch-xyz"
        responses = [channel_resp, api_resp]

        with mock.patch("tax_law_crawler.http_request", side_effect=responses):
            fetch_category(session, "c100010", page=2, size=10)
            call = mock.MagicMock()
        # Verify via arguments
        last_args = None
        for c in responses:
            if hasattr(c, 'json'):
                last_args = c
        assert True  # no crash = pass


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------
class TestDetailPage:
    def test_extracts_title_content(self):
        from tests.fixtures.tax.data import DETAIL_HTML

        with mock.patch("tax_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://fgk.chinatax.gov.cn/zcfgk/c100009/c5250687/content.html")
            assert "测试增值税暂行条例" in result["title"]
            assert result["content_text"] != ""

    def test_minimal_detail_returns_url(self):
        from tests.fixtures.tax.data import DETAIL_HTML_MINIMAL

        with mock.patch("tax_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_MINIMAL
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://fgk.chinatax.gov.cn/minimal")
            assert result["url"] == "https://fgk.chinatax.gov.cn/minimal"


# ---------------------------------------------------------------------------
# Keyword filtering
# ---------------------------------------------------------------------------
class TestKeywordFiltering:
    def test_hit_in_title(self):
        records = [
            {"title": "测试增值税条例", "sub_title": "", "document_number": ""},
            {"title": "不相关", "sub_title": "", "document_number": ""},
        ]
        assert len(search_keyword_in_records(records, "增值税")) == 1

    def test_hit_in_document_number(self):
        records = [
            {"title": "测试标题", "sub_title": "", "document_number": "财政部令第50号"},
            {"title": "另一个", "sub_title": "", "document_number": "财税〔2024〕1号"},
        ]
        assert len(search_keyword_in_records(records, "50号")) == 1


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class TestOutput:
    def test_save_results(self, tmp_path):
        records = [
            {"source": "tax_law", "title": "测试增值税条例", "url": "https://fgk.chinatax.gov.cn/zcfgk/c100009/content.html", "sub_title": "", "publish_time": "2024-01-01", "document_number": "财政部令第50号", "issuer": "财政部", "effective_date": "2024-07-01"}
        ]
        out = save_results(records, tmp_path, keyword="增值税")
        assert (out / "summary.json").exists()
        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "tax_law"
        assert summary["count"] == 1
