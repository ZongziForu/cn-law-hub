"""Live smoke tests — skipped by default. Set CN_LAW_RUN_LIVE=1 to run.

Each source gets a single minimal query (size=1-2). No pagination, no downloads.
"""

import os
import sys

import pytest

LIVE = os.getenv("CN_LAW_RUN_LIVE", "0") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set CN_LAW_RUN_LIVE=1 to run live tests")


@pytest.mark.live
class TestLiveGovPolicy:
    def test_search_returns_results(self):
        from gov_policy_library import search_collect

        records = search_collect("营商环境", max_items=2, timeout=30)
        assert len(records) > 0, "No results — try a broader keyword"
        assert records[0]["title"] != ""
        assert "gov.cn" in records[0].get("url", "")


@pytest.mark.live
class TestLiveMoJ:
    def test_search_returns_results(self):
        from moj_law_crawler import search_collect

        records = search_collect("行政", max_items=2, timeout=30)
        assert len(records) > 0
        assert records[0]["title"] != ""
        assert records[0].get("detail_url", "").startswith("http")


@pytest.mark.live
class TestLiveParty:
    def test_category_returns_results(self):
        from party_law_crawler import search_collect

        records = search_collect(category="条例", max_items=2, timeout=30)
        assert len(records) > 0
        assert records[0]["title"] != ""
        assert "12371.cn" in records[0].get("url", "")


@pytest.mark.live
class TestLiveMOD:
    def test_category_returns_results(self):
        from mod_law_crawler import fetch_full_list_page

        records = fetch_full_list_page("flfg", timeout=30)
        if records:
            assert records[0]["title"] != ""
            assert "mod.gov.cn" in records[0].get("url", "")


@pytest.mark.live
class TestLiveTax:
    def test_search_returns_results(self):
        from tax_law_crawler import CHANNEL_ID_CACHE, create_session, search_collect

        CHANNEL_ID_CACHE.clear()
        session = create_session()
        records = search_collect(session, keyword="增值税", max_items=2, timeout=30)
        assert len(records) > 0
        assert records[0]["title"] != ""
        assert "chinatax.gov.cn" in records[0].get("url", "")


@pytest.mark.live
class TestLiveMEE:
    def test_search_returns_results(self):
        from mee_law_crawler import search_collect

        records = search_collect(category="法律", max_items=2, timeout=30)
        assert len(records) > 0
        assert records[0]["title"] != ""
        assert "mee.gov.cn" in records[0].get("url", "")


@pytest.mark.live
class TestLiveCourt:
    def test_search_returns_results(self):
        from court_law_crawler import search_collect

        records = search_collect(category="司法解释", max_items=2, timeout=30)
        assert len(records) > 0
        assert records[0]["title"] != ""
        assert "court.gov.cn" in records[0].get("url", "")
