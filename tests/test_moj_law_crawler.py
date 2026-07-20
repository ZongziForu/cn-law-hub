"""Tests for scripts/moj_law_crawler.py — 司法部行政法规库."""

import json
from unittest import mock

import pytest

from moj_law_crawler import (
    STATUS_MAP,
    _cache,
    build_parser,
    fetch_detail,
    fetch_search_page,
    parse_search_results,
    save_results,
    search_collect,
)


@pytest.fixture(autouse=True)
def clear_moj_cache():
    _cache.clear()
    yield


class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "行政处罚"])
        assert args.search == "行政处罚"
        assert args.size == 20
        assert args.range == "title"
        assert args.status == "all"
        assert args.output == "./moj_law_output"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_range_content(self):
        args = build_parser().parse_args(["--search", "x", "--range", "content"])
        assert args.range == "content"

    def test_status_effective(self):
        args = build_parser().parse_args(["--search", "x", "--status", "effective"])
        assert args.status == "effective"

    def test_invalid_status_fails(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--search", "x", "--status", "bogus"])


class TestStatusMapping:
    def test_status_map(self):
        assert STATUS_MAP["all"] == ""
        assert STATUS_MAP["effective"] == "1"
        assert STATUS_MAP["invalid"] == "2"


class TestSearchRequestParams:
    def test_keyword_and_pagination_passed(self):
        with mock.patch("moj_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = '<html><input id="page-count" value="1"/></html>'
            mock_http.return_value = mock_resp

            fetch_search_page("测试", page=2, page_size=10, search_range="title")
            params = mock_http.call_args[1]["params"]
            assert params["SearchWord"] == "测试"
            assert params["pageIndex"] == 2
            assert params["pageSize"] == 10
            assert params["searchField"] == "1"

    def test_content_range_maps_to_2(self):
        with mock.patch("moj_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = '<html><input id="page-count" value="1"/></html>'
            mock_http.return_value = mock_resp

            fetch_search_page("测试", search_range="content")
            assert mock_http.call_args[1]["params"]["searchField"] == "2"

    def test_effective_status_mapped(self):
        with mock.patch("moj_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = '<html><input id="page-count" value="1"/></html>'
            mock_http.return_value = mock_resp

            fetch_search_page("测试", status="effective")
            assert mock_http.call_args[1]["params"]["effect"] == "1"

    def test_all_status_omitted(self):
        with mock.patch("moj_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = '<html><input id="page-count" value="1"/></html>'
            mock_http.return_value = mock_resp

            fetch_search_page("测试", status="all")
            assert "effect" not in mock_http.call_args[1]["params"]


class TestResultsParsing:
    def test_parse_extracts_all_fields(self):
        from tests.fixtures.moj.data import SEARCH_HTML

        records, total_pages = parse_search_results(SEARCH_HTML)
        assert len(records) == 3
        assert total_pages == 2

        first = records[0]
        assert "测试行政处罚法实施条例" in first["title"]
        assert first["publish_date"] == "2024-03-01"
        assert first["effective_date"] == "2024-05-01"
        assert first["status"] == "现行有效"
        assert first["detail_url"].startswith("https://xzfg.moj.gov.cn/detail?bbh=1")
        assert first["source"] == "moj_law"

    def test_parse_modified_status(self):
        from tests.fixtures.moj.data import SEARCH_HTML

        records, _ = parse_search_results(SEARCH_HTML)
        assert records[1]["status"] == "已修改"

    def test_parse_no_status(self):
        from tests.fixtures.moj.data import SEARCH_HTML

        records, _ = parse_search_results(SEARCH_HTML)
        third = records[2]
        assert third["status"] == "" or "无" in third.get("status", "")
        assert third["effective_date"] == "2023-08-01"

    def test_empty_html(self):
        from tests.fixtures.moj.data import SEARCH_HTML_EMPTY

        records, pages = parse_search_results(SEARCH_HTML_EMPTY)
        assert records == []
        assert pages == 0

    def test_no_results_html(self):
        from tests.fixtures.moj.data import SEARCH_HTML_NO_RESULTS

        records, pages = parse_search_results(SEARCH_HTML_NO_RESULTS)
        assert records == []
        assert pages == 1


class TestDetailPage:
    def test_extracts_title_content(self):
        from tests.fixtures.moj.data import DETAIL_HTML

        with mock.patch("moj_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://xzfg.moj.gov.cn/detail?bbh=1001")
            assert "测试行政处罚法实施条例" in result["title"]
            assert result["content_text"] != ""
            assert "full_html" in result  # unique to MoJ

    def test_minimal_detail_still_returns_url(self):
        from tests.fixtures.moj.data import DETAIL_HTML_MINIMAL

        with mock.patch("moj_law_crawler.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_MINIMAL
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail("https://xzfg.moj.gov.cn/detail?bbh=9999")
            assert result["url"] == "https://xzfg.moj.gov.cn/detail?bbh=9999"


class TestSearchCollect:
    def test_size_limits_across_pages(self):
        from tests.fixtures.moj.data import SEARCH_HTML

        with mock.patch("moj_law_crawler.fetch_search_page") as mock_fetch:
            mock_fetch.return_value = SEARCH_HTML
            records = search_collect("测试", max_items=2)
            assert len(records) <= 2


class TestOutput:
    def test_save_results_creates_all_files(self, tmp_path):
        records = [
            {
                "source": "moj_law",
                "title": "测试法规一",
                "detail_url": "https://xzfg.moj.gov.cn/detail?bbh=1001",
                "publish_date": "2024-03-01",
                "effective_date": "2024-05-01",
                "status": "现行有效",
            }
        ]

        out = save_results(records, tmp_path, keyword="测试")
        assert (out / "metadata.jsonl").exists()
        assert (out / "metadata.csv").exists()
        assert (out / "stats_report.json").exists()
        assert (out / "stats_report.md").exists()
        assert (out / "summary.json").exists()

        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "moj_law"
        assert summary["count"] == 1
