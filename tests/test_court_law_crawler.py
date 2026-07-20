"""Tests for scripts/court_law_crawler.py — 最高人民法院发布栏目."""

import json
from unittest import mock

import pytest

from court_law_crawler import (
    CATEGORY_MAP,
    CATEGORY_NAMES,
    _cache,
    build_parser,
    fetch_detail,
    fetch_list_page,
    parse_list_page,
    save_results,
    search_collect,
    search_keyword_in_records,
)


@pytest.fixture(autouse=True)
def clear_court_cache():
    _cache.clear()
    yield


class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "建设工程"])
        assert args.search == "建设工程"
        assert args.size == 20
        assert args.category == "全部"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_category_sifa_jieshi(self):
        args = build_parser().parse_args(["--category", "司法解释", "--size", "50"])
        assert args.category == "司法解释"

    def test_category_sifa_wenjian(self):
        args = build_parser().parse_args(["--category", "司法文件", "--size", "30"])
        assert args.category == "司法文件"

    def test_invalid_category_fails(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--search", "x", "--category", "不存在的栏目"])


class TestCategoryMapping:
    def test_interp_id(self):
        assert CATEGORY_MAP["司法解释"] == "16"
        assert CATEGORY_NAMES["16"] == "司法解释"

    def test_file_id(self):
        assert CATEGORY_MAP["司法文件"] == "17"

    def test_non_legal_categories(self):
        """重大案件, 通知, 司法数据 must not be marked as 司法解释."""
        assert CATEGORY_MAP["重大案件"] != "16"
        assert CATEGORY_MAP["通知"] != "16"
        assert CATEGORY_MAP["司法数据"] != "16"


class TestListPageURIConstruction:
    def test_page1_url(self):
        with mock.patch("court_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = "<html></html>"
            mock_http.return_value = mock_resp

            fetch_list_page("16", page=1)
            url = mock_http.call_args[0][1]
            assert url.endswith("16.html")
            assert "_" not in url.split("/")[-1].replace("16.html", "")

    def test_pageN_url(self):
        with mock.patch("court_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = "<html></html>"
            mock_http.return_value = mock_resp

            fetch_list_page("16", page=3)
            url = mock_http.call_args[0][1]
            assert "16_3.html" in url


class TestListPageParsing:
    def test_parse_returns_records_and_pages(self):
        from tests.fixtures.court.data import LIST_HTML_PAGE1_INTERP

        records, total_pages = parse_list_page(LIST_HTML_PAGE1_INTERP)
        assert len(records) >= 2
        assert total_pages == 5  # from 尾页 link
        first = records[0]
        assert "测试关于审理建设工程" in first["title"]
        assert first["url"].startswith("https://www.court.gov.cn/fabu/xiangqing/")
        assert first["source"] == "court_law"

    def test_relative_url_resolved(self):
        from tests.fixtures.court.data import LIST_HTML_PAGE1_INTERP

        records, _ = parse_list_page(LIST_HTML_PAGE1_INTERP)
        for r in records:
            assert r["url"].startswith("https://www.court.gov.cn")

    def test_empty_page(self):
        from tests.fixtures.court.data import LIST_HTML_EMPTY

        records, pages = parse_list_page(LIST_HTML_EMPTY)
        assert records == []
        assert pages == 0


class TestKeywordFiltering:
    def test_hit_in_title(self):
        records = [
            {"title": "测试建设工程纠纷司法解释"},
            {"title": "不相关的文件"},
        ]
        filtered = search_keyword_in_records(records, "建设工程")
        assert len(filtered) == 1

    def test_empty_keyword_returns_all(self):
        records = [{"title": "a"}]
        assert len(search_keyword_in_records(records, "")) == 1


class TestDetailPage:
    def test_extracts_title_date_source(self):
        from tests.fixtures.court.data import DETAIL_HTML

        with mock.patch("court_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://www.court.gov.cn/fabu/xiangqing/504221.html")
            assert "建设工程" in result["title"]
            assert result["publish_date"] != ""
            assert "最高人民法院" in result["source"]

    def test_no_source_no_crash(self):
        from tests.fixtures.court.data import DETAIL_HTML_NO_SOURCE

        with mock.patch("court_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_NO_SOURCE
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://www.court.gov.cn/fabu/xiangqing/504299.html")
            assert result["title"] == "测试标题"
            assert result["url"] != ""


class TestSearchCollect:
    def test_size_limit(self):
        from tests.fixtures.court.data import LIST_HTML_PAGE1_INTERP

        with mock.patch("court_law_crawler.fetch_list_page") as mock_fetch:
            mock_fetch.return_value = LIST_HTML_PAGE1_INTERP
            records = search_collect(category="司法解释", max_items=1)
            assert len(records) <= 1

    def test_default_categories(self):
        """When '全部', only 司法解释(16) and 司法文件(17) are fetched — not all."""
        with mock.patch("court_law_crawler.fetch_list_page") as mock_fetch:
            mock_fetch.return_value = "<html></html>"
            search_collect(category="全部", max_items=1)
            cat_ids_called = {c[0][0] for c in mock_fetch.call_args_list}
            # Should only call "16" and "17" for "全部"
            assert "16" in cat_ids_called
            assert "15" not in cat_ids_called  # 重大案件 not default


class TestOutput:
    def test_save_results(self, tmp_path):
        records = [
            {"source": "court_law", "title": "测试司法解释", "url": "https://www.court.gov.cn/fabu/xiangqing/504221.html", "category": "司法解释"}
        ]
        out = save_results(records, tmp_path)
        assert (out / "summary.json").exists()
        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "court_law"
        assert summary["count"] == 1
