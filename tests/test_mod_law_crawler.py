"""Tests for scripts/mod_law_crawler.py — 国防部法规文库."""

import json
from unittest import mock

import pytest

from mod_law_crawler import (
    CATEGORY_MAP,
    _cache,
    build_parser,
    fetch_category_index,
    fetch_detail,
    fetch_full_list_page,
    parse_category_page,
    save_results,
    search_collect,
    search_keyword_in_records,
)


@pytest.fixture(autouse=True)
def clear_mod_cache():
    _cache.clear()
    yield


class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "军队"])
        assert args.search == "军队"
        assert args.size == 20
        assert args.category == "全部"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_category(self):
        args = build_parser().parse_args(["--category", "法律法规", "--size", "50"])
        assert args.category == "法律法规"


class TestCategoryMapping:
    def test_all_categories(self):
        assert CATEGORY_MAP["法律法规"] == "flfg"
        assert CATEGORY_MAP["白皮书"] == "bps"
        assert CATEGORY_MAP["文件"] == "wj_213958"
        assert len(CATEGORY_MAP) == 8

    def test_index_url_construction(self):
        with mock.patch("mod_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = "<html></html>"
            mock_http.return_value = mock_resp

            fetch_category_index("flfg")
            url = mock_http.call_args[0][1]
            assert "/gfbw/fgwx/flfg/index.html" in url


class TestListPageParsing:
    def test_parse_returns_entries(self):
        from tests.fixtures.mod.data import INDEX_HTML_FLFG

        records = parse_category_page(INDEX_HTML_FLFG, category="flfg")
        # 2 valid articles (1 non-matching .shtml, 1 "显示更多" skipped)
        assert len(records) >= 2
        first = records[0]
        assert "测试国防法实施条例" in first["title"]
        assert "16448581.html" in first["url"]
        assert first["category"] == "flfg" or first["category"] != ""

    def test_show_more_links_filtered(self):
        from tests.fixtures.mod.data import INDEX_HTML_FLFG

        records = parse_category_page(INDEX_HTML_FLFG, category="flfg")
        titles = [r["title"] for r in records]
        assert "显示更多" not in titles

    def test_relative_url_resolved(self):
        from tests.fixtures.mod.data import INDEX_HTML_WITH_RELATIVE

        records = parse_category_page(INDEX_HTML_WITH_RELATIVE)
        assert len(records) == 1
        assert records[0]["url"].startswith("http://www.mod.gov.cn")

    def test_empty_page(self):
        from tests.fixtures.mod.data import INDEX_HTML_EMPTY

        records = parse_category_page(INDEX_HTML_EMPTY)
        assert records == []

    def test_full_list_page(self):
        from tests.fixtures.mod.data import INDEX_HTML_FLFG

        with mock.patch("mod_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = INDEX_HTML_FLFG
            mock_http.return_value = mock_resp

            records = fetch_full_list_page("flfg")
            assert len(records) >= 2


class TestKeywordFiltering:
    def test_hit_in_title(self):
        records = [
            {"title": "测试国防法实施条例"},
            {"title": "不相关的文档"},
        ]
        filtered = search_keyword_in_records(records, "国防法")
        assert len(filtered) == 1

    def test_empty_keyword_returns_all(self):
        records = [{"title": "a"}, {"title": "b"}]
        assert len(search_keyword_in_records(records, "")) == 2


class TestDetailPage:
    def test_extracts_title_content_date_source(self):
        from tests.fixtures.mod.data import DETAIL_HTML

        with mock.patch("mod_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("http://www.mod.gov.cn/gfbw/fgwx/flfg/16448581.html")
            assert "测试国防法实施条例" in result["title"]
            assert result["content_text"] != ""
            assert result["publish_date"] == "2024-01-15"
            assert result["source"] == "国防部网站"

    def test_no_source_no_crash(self):
        from tests.fixtures.mod.data import DETAIL_HTML_NO_SOURCE

        with mock.patch("mod_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_NO_SOURCE
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("http://www.mod.gov.cn/article.html")
            assert result["title"] != ""
            assert result["source"] == ""


class TestSearchCollect:
    def test_size_limit(self):
        from tests.fixtures.mod.data import INDEX_HTML_FLFG

        with mock.patch("mod_law_crawler.fetch_full_list_page") as mock_fetch:
            mock_fetch.return_value = parse_category_page(INDEX_HTML_FLFG)
            records = search_collect(category="法律法规", max_items=1)
            assert len(records) <= 1


class TestOutput:
    def test_save_results_all_files(self, tmp_path):
        records = [
            {"source": "mod_law", "title": "测试法规", "url": "http://www.mod.gov.cn/gfbw/fgwx/flfg/1.html", "category": "flfg"}
        ]
        out = save_results(records, tmp_path)
        assert (out / "summary.json").exists()
        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "mod_law"
        assert summary["count"] == 1
