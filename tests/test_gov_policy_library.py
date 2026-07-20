"""Tests for scripts/gov_policy_library.py — 国务院政策文件库."""

import json
from pathlib import Path
from unittest import mock

import pytest

from gov_policy_library import (
    CATEGORY_MAP,
    _cache,
    build_parser,
    fetch_detail_page,
    parse_search_results,
    save_results,
    search_collect,
    search_policies,
)


@pytest.fixture(autouse=True)
def clear_gov_cache():
    _cache.clear()
    yield


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class TestCLI:
    def test_help(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--help"])

    def test_defaults(self):
        args = build_parser().parse_args(["--search", "营商环境"])
        assert args.search == "营商环境"
        assert args.size == 20
        assert args.range == "title"
        assert args.sort == "score"
        assert args.output == "./gov_policy_output"
        assert args.rate_limit == "auto"

    def test_size_1(self):
        args = build_parser().parse_args(["--search", "x", "--size", "1"])
        assert args.size == 1

    def test_content_range(self):
        args = build_parser().parse_args(["--search", "x", "--range", "content"])
        assert args.range == "content"

    def test_category_year_dept(self):
        args = build_parser().parse_args(
            ["--search", "x", "--category", "国务院文件", "--year", "2024", "--department", "国务院"]
        )
        assert args.category == "国务院文件"
        assert args.year == "2024"
        assert args.department == "国务院"

    def test_invalid_category_fails(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--search", "x", "--category", "不存在的分类"])


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------
class TestRequestConstruction:
    def test_title_search_params(self):
        """Verify searchfield=title is sent for title-range search."""
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "code": 200,
                "searchVO": {"totalCount": 0, "catMap": {}},
            }
            mock_http.return_value = mock_resp

            search_policies("test", search_field="title")
            call_kwargs = mock_http.call_args
            assert call_kwargs[0][0] == "GET"
            assert "search-gov/data" in call_kwargs[0][1]
            assert call_kwargs[1]["params"]["searchfield"] == "title"

    def test_content_search_params(self):
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "code": 200,
                "searchVO": {"totalCount": 0, "catMap": {}},
            }
            mock_http.return_value = mock_resp

            search_policies("test", search_field="content")
            assert mock_http.call_args[1]["params"]["searchfield"] == "content"

    def test_category_mapping(self):
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "code": 200,
                "searchVO": {"totalCount": 0, "catMap": {}},
            }
            mock_http.return_value = mock_resp

            search_policies("test", category="gongwen")
            assert mock_http.call_args[1]["params"]["childtype"] == "gongwen"

    def test_year_passed(self):
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "code": 200,
                "searchVO": {"totalCount": 0, "catMap": {}},
            }
            mock_http.return_value = mock_resp

            search_policies("test", year="2024")
            assert mock_http.call_args[1]["params"]["pubtimeyear"] == "2024"

    def test_page_size_sort_passed(self):
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "code": 200,
                "searchVO": {"totalCount": 0, "catMap": {}},
            }
            mock_http.return_value = mock_resp

            search_policies("test", page=2, size=20, sort="pubtime")
            params = mock_http.call_args[1]["params"]
            assert params["p"] == 2
            assert params["n"] == 20
            assert params["sort"] == "pubtime"

    def test_api_url_correct(self):
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.json.return_value = {
                "code": 200,
                "searchVO": {"totalCount": 0, "catMap": {}},
            }
            mock_http.return_value = mock_resp

            search_policies("test")
            url = mock_http.call_args[0][1]
            assert url.startswith("https://sousuo.www.gov.cn/search-gov/data")

    def test_category_name_to_code(self):
        assert CATEGORY_MAP["国务院文件"] == "gongwen"
        assert CATEGORY_MAP["国务院部门文件"] == "bumenfile"
        assert CATEGORY_MAP["解读"] == "otherfile"
        assert CATEGORY_MAP["全部"] == ""


# ---------------------------------------------------------------------------
# Results parsing
# ---------------------------------------------------------------------------
class TestResultsParsing:
    def test_parse_results_extracts_fields(self):
        from tests.fixtures.gov_policy.data import SEARCH_RESPONSE

        results = parse_search_results(SEARCH_RESPONSE)
        assert len(results) >= 3
        first = results[0]
        assert "测试" in first["title"]
        assert "<em>" not in first["title"]  # highlight tags cleaned
        assert first["url"] == "https://www.gov.cn/gongbao/content/2024/content_12345.htm"
        assert first["pub_time"] == "2024-03-15"
        assert first["department"] == "国务院"
        assert first["source"] == "gov_policy_library"

    def test_parse_results_handles_missing_fields(self):
        from tests.fixtures.gov_policy.data import SEARCH_RESPONSE

        results = parse_search_results(SEARCH_RESPONSE)
        second = results[1]
        assert second["title"] == "测试政策二进一步推进放管服改革"
        assert second["code"] == "gf002"
        assert "summary" in second  # field exists even if empty
        assert "pcode" in second

    def test_parse_results_missing_url(self):
        from tests.fixtures.gov_policy.data import SEARCH_RESPONSE

        results = parse_search_results(SEARCH_RESPONSE)
        third = results[2]
        assert third["url"] == ""  # empty piclinksurl
        assert third["title"] != ""

    def test_empty_response(self):
        from tests.fixtures.gov_policy.data import EMPTY_RESPONSE

        results = parse_search_results(EMPTY_RESPONSE)
        assert results == []

    def test_error_response(self):
        from tests.fixtures.gov_policy.data import SEARCH_ERROR_RESPONSE

        results = parse_search_results(SEARCH_ERROR_RESPONSE)
        assert results == []

    def test_no_validity_claim_generated(self):
        """Policy results must not invent a '现行有效' status."""
        from tests.fixtures.gov_policy.data import SEARCH_RESPONSE

        results = parse_search_results(SEARCH_RESPONSE)
        for r in results:
            # parse_search_results does not add status fields — policy status
            # is not determined from search results alone
            assert "status" not in r or r.get("status") in ("", None)


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------
class TestDetailPage:
    def test_extracts_title_content_date_source(self):
        from tests.fixtures.gov_policy.data import DETAIL_HTML_FULL

        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_FULL
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail_page("https://www.gov.cn/test.htm")
            assert "测试法规一" in result["title"]
            assert "优化营商环境" in result["content_text"]
            assert result["publish_date"] == "2024-03-15"
            assert result["source"] == "国务院"

    def test_detail_without_content_still_returns_meta(self):
        from tests.fixtures.gov_policy.data import DETAIL_HTML_NO_CONTENT

        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = DETAIL_HTML_NO_CONTENT
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            result = fetch_detail_page("https://www.gov.cn/test.htm")
            assert result["title"] == "测试标题"
            assert result["url"] == "https://www.gov.cn/test.htm"

    def test_detail_cache_hit(self):
        with mock.patch("gov_policy_library.http_request") as mock_http:
            mock_resp = mock.MagicMock()
            mock_resp.text = "<html></html>"
            mock_resp.encoding = "utf-8"
            mock_http.return_value = mock_resp

            # First call
            fetch_detail_page("https://www.gov.cn/test.htm")
            # Second call — cached
            fetch_detail_page("https://www.gov.cn/test.htm")
            # Should only have requested once
            assert mock_http.call_count == 1


# ---------------------------------------------------------------------------
# Search collect
# ---------------------------------------------------------------------------
class TestSearchCollect:
    def test_size_limit_stops_collection(self):
        from tests.fixtures.gov_policy.data import SEARCH_RESPONSE

        with mock.patch("gov_policy_library.search_policies") as mock_search:
            mock_search.return_value = SEARCH_RESPONSE

            records = search_collect("测试", max_items=2)
            assert len(records) <= 2

    def test_empty_result_returns_empty_list(self):
        from tests.fixtures.gov_policy.data import EMPTY_RESPONSE

        with mock.patch("gov_policy_library.search_policies") as mock_search:
            mock_search.return_value = EMPTY_RESPONSE

            records = search_collect("不存在的关键词")
            assert records == []


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
class TestOutput:
    def test_save_results_creates_all_files(self, tmp_path):
        records = [
            {
                "source": "gov_policy_library",
                "title": "测试法规一",
                "url": "https://www.gov.cn/test1",
                "department": "国务院",
                "category": "国务院文件",
                "pub_time": "2024-03-15",
            },
            {
                "source": "gov_policy_library",
                "title": "测试法规二",
                "url": "https://www.gov.cn/test2",
                "department": "国家发展改革委",
                "category": "国务院部门文件",
                "pub_time": "2024-01-01",
            },
        ]

        out = save_results(records, tmp_path, keyword="测试")
        assert out.exists()
        assert (out / "metadata.jsonl").exists()
        assert (out / "metadata.csv").exists()
        assert (out / "stats_report.json").exists()
        assert (out / "stats_report.md").exists()
        assert (out / "summary.json").exists()

        summary = json.loads((out / "summary.json").read_text())
        assert summary["source"] == "gov_policy_library"
        assert summary["count"] == 2

    def test_save_results_empty_records(self, tmp_path):
        out = save_results([], tmp_path, keyword="测试")
        stats = json.loads((out / "stats_report.json").read_text())
        assert stats["record_count"] == 0
