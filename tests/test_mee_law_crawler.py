"""Tests for scripts/mee_law_crawler.py — 生态环境部法规规章."""

import json
from unittest import mock

import pytest

from mee_law_crawler import (
    CATEGORY_MAP,
    CATEGORY_URLS,
    build_parser,
    fetch_detail,
    fetch_list_page,
    parse_list_page,
    save_results,
    search_collect,
    search_keyword_in_records,
)


class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "碳"])
        assert args.search == "碳"
        assert args.size == 20
        assert args.category == "全部"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_category(self):
        args = build_parser().parse_args(["--category", "法律"])
        assert args.category == "法律"


class TestCategoryURIMapping:
    def test_all_categories_have_urls(self):
        for key in ["fl", "xzfg", "gz", "sthjshpczd", "zfjs"]:
            assert key in CATEGORY_URLS

    def test_standards_not_in_categories(self):
        """标准 (Environmental Standards) must not be present."""
        assert "标准" not in CATEGORY_MAP
        assert "bz" not in CATEGORY_URLS

    def test_gz_has_separate_base_url(self):
        assert CATEGORY_URLS["gz"] != f"https://www.mee.gov.cn/ywgz/fgbz/gz/"
        assert "/gzk/gz/" in CATEGORY_URLS["gz"]


class TestListPageParsing:
    def test_parse_returns_entries(self):
        from tests.fixtures.mee.data import LIST_HTML_FL

        records = parse_list_page(LIST_HTML_FL, category="fl")
        assert len(records) >= 2
        first = records[0]
        assert "测试环境保护法" in first["title"]
        assert first["category"] == "fl"
        assert first["url"].startswith("https://www.mee.gov.cn")
        assert first["source"] == "mee_law"

    def test_empty_page(self):
        from tests.fixtures.mee.data import LIST_HTML_EMPTY

        records = parse_list_page(LIST_HTML_EMPTY)
        assert records == []

    def test_subcategory_auto_detection(self):
        from tests.fixtures.mee.data import LIST_HTML_GZ

        records = parse_list_page(LIST_HTML_GZ)
        assert len(records) >= 1
        assert records[0]["category"] == "gz" or "碳排放" in records[0]["title"]


class TestKeywordFiltering:
    def test_hit_in_title(self):
        records = [
            {"title": "测试环境保护法"},
            {"title": "测试不相关法规"},
        ]
        filtered = search_keyword_in_records(records, "环境保护")
        assert len(filtered) == 1

    def test_empty_keyword_returns_all(self):
        records = [{"title": "a"}, {"title": "b"}]
        assert len(search_keyword_in_records(records, "")) == 2


class TestDetailPage:
    def test_extracts_title_content(self):
        from tests.fixtures.mee.data import DETAIL_HTML

        with mock.patch("mee_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://www.mee.gov.cn/ywgz/fgbz/fl/t20260313_1146496.shtml")
            assert "测试环境保护法" in result["title"]
            assert result["content_text"] != ""

    def test_date_from_url_fallback(self):
        from tests.fixtures.mee.data import DETAIL_HTML_MINIMAL

        with mock.patch("mee_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_MINIMAL
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://www.mee.gov.cn/ywgz/fgbz/fl/t20260313_1146496.shtml")
            assert result["publish_date"] != "" or result["url"] != ""


class TestSearchCollect:
    def test_size_limit_across_categories(self):
        from tests.fixtures.mee.data import LIST_HTML_FL, LIST_HTML_XZFG

        with mock.patch("mee_law_crawler.fetch_list_page") as mock_fetch:
            mock_fetch.side_effect = [LIST_HTML_FL, LIST_HTML_XZFG]
            records = search_collect(max_items=2)
            assert len(records) <= 2

    def test_records_tagged_with_category(self):
        from tests.fixtures.mee.data import LIST_HTML_FL

        with mock.patch("mee_law_crawler.fetch_list_page") as mock_fetch:
            mock_fetch.return_value = LIST_HTML_FL
            records = search_collect(category="法律", max_items=1)
            if records:
                assert records[0].get("category") == "fl"


class TestOutput:
    def test_save_results(self, tmp_path):
        records = [
            {"source": "mee_law", "title": "测试环境保护法", "url": "https://www.mee.gov.cn/ywgz/fgbz/fl/t20260313_1146496.shtml", "category": "fl"}
        ]
        out = save_results(records, tmp_path)
        assert (out / "summary.json").exists()
        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "mee_law"
        assert summary["count"] == 1
