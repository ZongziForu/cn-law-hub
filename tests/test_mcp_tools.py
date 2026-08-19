"""Tests for scripts/mcp_server.py — MCP tool routing & output shape.

Requires the optional MCP dependency: `pip install "mcp>=2.0.0"`.
Network calls are fully mocked; only routing/param-shaping is exercised.
"""

import io
from unittest import mock

import pytest

import mcp_server


@pytest.fixture(autouse=True)
def reset_state():
    """Each test starts with a fresh (un-cached) AthenaAuth singleton."""
    mcp_server._athena_auth = None
    yield


# ── search_laws routing ──────────────────────────────────────────────────

class TestSearchLawsRouting:
    def test_moj_routes_and_tags_source(self):
        with mock.patch.object(
            mcp_server.moj_law_crawler, "search_collect", return_value=[{"title": "A"}]
        ):
            result = mcp_server.search_laws("moj", keyword="民法典")
        assert result["source"] == "moj"
        assert result["count"] == 1
        assert result["records"][0]["source"] == "moj"

    def test_party_passes_category(self):
        with mock.patch.object(mcp_server.party_law_crawler, "search_collect") as sc:
            mcp_server.search_laws("party", keyword="纪律", category="党章", size=5)
        sc.assert_called_once_with("纪律", category="党章", max_items=5)

    def test_gov_policy_does_not_require_category(self):
        with mock.patch.object(mcp_server.gov_policy_library, "search_collect") as sc:
            result = mcp_server.search_laws("gov_policy", keyword="环保")
        sc.assert_called_once_with("环保", max_items=20)
        assert "error" not in result

    def test_tax_creates_session_first(self):
        with mock.patch.object(mcp_server.tax_law_crawler, "create_session",
                               return_value="SESS") as cs, \
             mock.patch.object(mcp_server.tax_law_crawler, "search_collect") as sc:
            mcp_server.search_laws("tax", keyword="增值税")
        cs.assert_called_once()
        sc.assert_called_once_with("SESS", "增值税", category="", max_items=20)

    def test_gov_rules_requires_category(self):
        result = mcp_server.search_laws("gov_rules", keyword="环保")
        assert result["count"] == 0
        assert "error" in result and "category" in result["error"]

    def test_gov_rules_creates_auth_and_searches(self):
        fake_auth = object()
        with mock.patch.object(mcp_server, "_get_athena_auth", return_value=fake_auth) as ga, \
             mock.patch.object(mcp_server.gov_rules_crawler, "search_category") as sc:
            mcp_server.search_laws("gov_rules", keyword="管理", category="部门规章", size=3)
        ga.assert_called_once()
        sc.assert_called_once_with(fake_auth, "部门规章", keyword="管理", max_items=3)

    def test_treaty_requires_category(self):
        result = mcp_server.search_laws("treaty", keyword="上合")
        assert "error" in result and "category" in result["error"]

    def test_treaty_uses_collection_name(self):
        with mock.patch.object(mcp_server.treaty_crawler, "search_collection") as sc:
            mcp_server.search_laws("treaty", keyword="上合", category="双边", size=2)
        sc.assert_called_once_with("双边", keyword="上合", max_items=2)

    def test_unknown_source_returns_error(self):
        result = mcp_server.search_laws("bogus")
        assert "error" in result

    def test_npc_extracts_rows(self):
        data = {"code": 200, "rows": [{"bbbs": "1"}, {"bbbs": "2"}], "total": 2}
        with mock.patch.object(mcp_server.download, "search_laws", return_value=data) as sl:
            result = mcp_server.search_laws("npc", keyword="出租")
        sl.assert_called_once_with("出租", size=20)
        assert result["count"] == 2
        assert all(r["source"] == "npc" for r in result["records"])

    def test_crawler_exception_returned_as_error(self):
        with mock.patch.object(
            mcp_server.mee_law_crawler, "search_collect", side_effect=RuntimeError("boom")
        ):
            result = mcp_server.search_laws("mee", keyword="排污")
        assert result["count"] == 0
        assert "error" in result and "boom" in result["error"]

    def test_non_dict_record_wrapped(self):
        with mock.patch.object(mcp_server.court_law_crawler, "search_collect",
                               return_value=[("raw", "tuple")]):
            result = mcp_server.search_laws("court", keyword="执行")
        assert result["records"][0] == {"value": ("raw", "tuple"), "source": "court"}


class TestAthenaAuth:
    def test_lazy_singleton(self):
        with mock.patch.object(mcp_server.gov_rules_crawler, "AthenaAuth") as A:
            inst = A.return_value
            first = mcp_server._get_athena_auth()
            second = mcp_server._get_athena_auth()
            assert first is second
            A.assert_called_once()
            inst.discover.assert_called_once()


# ── get_law_detail routing ───────────────────────────────────────────────

class TestGetLawDetailRouting:
    def test_gov_policy_uses_fetch_detail_page(self):
        with mock.patch.object(
            mcp_server.gov_policy_library, "fetch_detail_page", return_value={"title": "T"}
        ) as fd:
            result = mcp_server.get_law_detail("gov_policy", "http://x")
        fd.assert_called_once_with("http://x")
        assert result["detail"] == {"title": "T"}

    def test_npc_passes_bbbs_id(self):
        with mock.patch.object(mcp_server.download, "fetch_detail",
                               return_value={"data": {}}) as fd:
            result = mcp_server.get_law_detail("npc", "2c909fdd")
        fd.assert_called_once_with("2c909fdd")
        assert result["source"] == "npc"

    def test_unknown_source(self):
        result = mcp_server.get_law_detail("nope", "http://x")
        assert "error" in result


# ── query_article ────────────────────────────────────────────────────────

class TestQueryArticle:
    def test_grep_search(self):
        with mock.patch.object(mcp_server.download, "_download_docx_text",
                               return_value=([], {"title": "L"})), \
             mock.patch.object(mcp_server, "split_into_articles",
                               return_value=[("第一条", "文本 经济补偿 文本"), ("第二条", "其他")]):
            result = mcp_server.query_article("id1", grep="经济补偿")
        assert result["title"] == "L"
        assert result["count"] == 1
        assert result["results"][0]["article_num"] == "第一条"

    def test_query_by_article_number(self):
        def fake_match(q, num):
            return q in num

        with mock.patch.object(mcp_server.download, "_download_docx_text",
                               return_value=([], {"title": "L"})), \
             mock.patch.object(mcp_server, "split_into_articles",
                               return_value=[("第三十八条", "text"), ("第一条", "text")]), \
             mock.patch.object(mcp_server, "match_article_query", side_effect=fake_match):
            result = mcp_server.query_article("id1", query="第三十八条")
        assert result["count"] == 1
        assert result["results"][0]["article_num"] == "第三十八条"

    def test_query_falls_back_to_prefix_match(self):
        with mock.patch.object(mcp_server.download, "_download_docx_text",
                               return_value=([], {"title": "L"})), \
             mock.patch.object(mcp_server, "split_into_articles",
                               return_value=[("第三十八条", "经济补偿 内容"), ("第一条", "x")]), \
             mock.patch.object(mcp_server, "match_article_query", return_value=False):
            result = mcp_server.query_article("id1", query="经济补偿")
        assert result["count"] == 1
        assert result["results"][0]["article_num"] == "第三十八条"

    def test_requires_query_or_grep(self):
        result = mcp_server.query_article("id1")
        assert "error" in result

    def test_download_error_returned_as_error(self):
        with mock.patch.object(mcp_server.download, "_download_docx_text",
                               side_effect=RuntimeError("network")):
            result = mcp_server.query_article("id1", grep="x")
        assert "error" in result and "network" in result["error"]


# ── preview_law ──────────────────────────────────────────────────────────

class TestPreviewLaw:
    def test_preview_structure(self):
        with mock.patch.object(mcp_server.download, "fetch_detail",
                               return_value={"data": {"content": {}}}), \
             mock.patch.object(mcp_server.download, "_detect_numbering_patterns",
                               return_value={"primary": "chinese", "sample_titles": ["第一条"]}), \
             mock.patch.object(mcp_server.download, "_download_docx_text",
                               return_value=(["p"], {"title": "L", "category": "法律"})), \
             mock.patch.object(mcp_server, "split_into_articles",
                               return_value=[("第一条", "正文内容较长的条目文本需要截断显示"), ("章", "总则")]), \
             mock.patch.object(mcp_server, "is_article_line",
                               side_effect=lambda n: n.startswith("第")):
            result = mcp_server.preview_law("id1")
        assert result["title"] == "L"
        assert result["article_count"] == 1
        assert result["numbering"] == "chinese"
        assert result["sample_titles"] == ["第一条"]
        assert len(result["preview"]) == 2
        assert result["preview"][0]["is_article"] is True

    def test_truncated_flag(self):
        articles = [(f"第{i}条", f"t{i}") for i in range(25)]
        with mock.patch.object(mcp_server.download, "fetch_detail", return_value={}), \
             mock.patch.object(mcp_server.download, "_detect_numbering_patterns",
                               return_value={"primary": "arabic", "sample_titles": []}), \
             mock.patch.object(mcp_server.download, "_download_docx_text",
                               return_value=([], {"title": "L"})), \
             mock.patch.object(mcp_server, "split_into_articles", return_value=articles), \
             mock.patch.object(mcp_server, "is_article_line", return_value=True):
            result = mcp_server.preview_law("id2")
        assert result["truncated"] is True
        assert len(result["preview"]) == 20


# ── article_search stdout hygiene ────────────────────────────────────────

class TestArticleSearch:
    def test_swallows_stdout(self):
        def fake(keyword, law_keyword=None, max_laws=5, context=0):
            print("STDOUT_POLLUTION_MARKER")
            return [{"title": "L", "articles": []}]

        with mock.patch.object(
            mcp_server.article_search_mod, "search_articles", side_effect=fake
        ) as sa:
            captured = io.StringIO()
            with mcp_server.contextlib.redirect_stdout(captured):
                result = mcp_server.article_search("违约金")
            assert result["count"] == 1
            assert result["laws"][0]["title"] == "L"
            # progress + result output must be captured, not leaked to real stdout
            assert "STDOUT_POLLUTION_MARKER" not in captured.getvalue()

    def test_exception_returned_as_error(self):
        with mock.patch.object(
            mcp_server.article_search_mod, "search_articles", side_effect=ValueError("bad")
        ):
            result = mcp_server.article_search("违约金")
        assert result["count"] == 0
        assert "error" in result
