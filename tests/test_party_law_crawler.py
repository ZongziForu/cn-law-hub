"""Tests for scripts/party_law_crawler.py — 党内法规库 (12371.cn)."""

import json
from unittest import mock

import pytest

from party_law_crawler import (
    CATEGORY_MAP,
    _cache,
    build_parser,
    fetch_category_page,
    fetch_detail,
    parse_category_page,
    save_results,
    search_collect,
    search_keyword_in_text,
)


@pytest.fixture(autouse=True)
def clear_party_cache():
    _cache.clear()
    yield


class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "纪律"])
        assert args.search == "纪律"
        assert args.size == 20
        assert args.category == "全部"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_category_tiaoli(self):
        args = build_parser().parse_args(["--category", "条例"])
        assert args.category == "条例"

    def test_invalid_category_fails(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--search", "x", "--category", "不存在的"])


class TestCategoryMapping:
    def test_all_categories(self):
        assert CATEGORY_MAP["全部"] == ""
        assert CATEGORY_MAP["党章"] == "zz"
        assert CATEGORY_MAP["条例"] == "tl"
        assert CATEGORY_MAP["规定"] == "gd"
        assert len(CATEGORY_MAP) == 11

    def test_category_url_construction(self):
        with mock.patch("party_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = "<html></html>"
            mock_http.return_value = mock_resp

            fetch_category_page(category="tl")
            url = mock_http.call_args[0][1]
            assert "/special/dnfg/tl/" in url


class TestListPageParsing:
    def test_parse_returns_entries(self):
        from tests.fixtures.party.data import LIST_HTML_TIAOLI

        records = parse_category_page(LIST_HTML_TIAOLI)
        assert len(records) == 3
        first = records[0]
        assert "测试纪律处分条例" in first["title"]
        assert first["url"].startswith("https://www.12371.cn/2024/03/15/ARTI")
        assert first["source"] == "party_law"

    def test_relative_urls_resolved(self):
        from tests.fixtures.party.data import LIST_HTML_TIAOLI

        records = parse_category_page(LIST_HTML_TIAOLI)
        for r in records:
            assert r["url"].startswith("https://www.12371.cn")

    def test_nav_links_filtered_out(self):
        from tests.fixtures.party.data import LIST_HTML_WITH_NAV

        records = parse_category_page(LIST_HTML_WITH_NAV)
        urls = [r["url"] for r in records]
        # Non-article links (javascript:, bare "/") should be filtered
        for url in urls:
            assert ".shtml" in url or "ARTI" in url

    def test_empty_page_returns_empty(self):
        from tests.fixtures.party.data import LIST_HTML_EMPTY

        records = parse_category_page(LIST_HTML_EMPTY)
        assert records == []

    def test_dedup_same_url(self):
        """Same URL appearing twice should be deduplicated."""
        html = """<html><body>
        <a href="/2024/01/01/ARTI001.shtml">测试条目</a>
        <a href="/2024/01/01/ARTI001.shtml">测试条目重复</a>
        </body></html>"""

        with mock.patch("party_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = html
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

        records = parse_category_page(html)
        assert len(records) == 1


class TestKeywordFiltering:
    def test_hit_in_title(self):
        records = [
            {"title": "测试纪律处分条例"},
            {"title": "测试党内监督条例"},
            {"title": "不相关的法规"},
        ]
        filtered = search_keyword_in_text(records, "纪律处分")
        assert len(filtered) == 1
        assert filtered[0]["title"] == "测试纪律处分条例"

    def test_empty_keyword_returns_all(self):
        records = [{"title": "a"}, {"title": "b"}]
        assert len(search_keyword_in_text(records, "")) == 2

    def test_no_match_returns_empty(self):
        records = [{"title": "测试条例"}]
        assert search_keyword_in_text(records, "不存在") == []


class TestDetailPage:
    def test_extracts_title_content_date(self):
        from tests.fixtures.party.data import DETAIL_HTML

        with mock.patch("party_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://www.12371.cn/2024/03/15/ARTI123.shtml")
            assert "测试纪律处分条例" in result["title"]
            assert result["content_text"] != ""
            assert result["publish_date"] == "2024-03-15"

    def test_date_from_url_fallback(self):
        from tests.fixtures.party.data import DETAIL_HTML_MINIMAL

        with mock.patch("party_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_MINIMAL
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://www.12371.cn/2024/06/15/ARTI999.shtml")
            assert result["publish_date"] == "2024-06-15"


class TestSearchCollect:
    def test_size_limit_stops(self):
        from tests.fixtures.party.data import LIST_HTML_TIAOLI

        with mock.patch("party_law_crawler.fetch_category_page") as mock_fetch:
            mock_fetch.return_value = LIST_HTML_TIAOLI
            records = search_collect(category="条例", max_items=2)
            assert len(records) <= 2

    def test_category_added_to_records(self):
        from tests.fixtures.party.data import LIST_HTML_TIAOLI

        with mock.patch("party_law_crawler.fetch_category_page") as mock_fetch:
            mock_fetch.return_value = LIST_HTML_TIAOLI
            records = search_collect(category="条例", max_items=1)
            assert records[0].get("category") == "tl"


class TestOutput:
    def test_save_results_creates_all_files(self, tmp_path):
        records = [
            {"source": "party_law", "title": "测试条例一", "url": "https://www.12371.cn/2024/01/ARTI001.shtml", "category": "tl"}
        ]
        out = save_results(records, tmp_path, keyword="测试")
        assert (out / "summary.json").exists()
        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "party_law"
        assert summary["count"] == 1
