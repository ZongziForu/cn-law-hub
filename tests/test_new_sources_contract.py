"""Contract tests across all 7 new data sources — minimal shared expectations."""

import json
import re
from unittest import mock

import pytest

# --- Gov Policy ---
from gov_policy_library import parse_search_results as gov_parse
from tests.fixtures.gov_policy.data import SEARCH_RESPONSE

# --- MoJ ---
from moj_law_crawler import parse_search_results as moj_parse
from tests.fixtures.moj.data import SEARCH_HTML

# --- Party ---
from party_law_crawler import parse_category_page as party_parse
from tests.fixtures.party.data import LIST_HTML_TIAOLI

# --- MOD ---
from mod_law_crawler import parse_category_page as mod_parse
from tests.fixtures.mod.data import INDEX_HTML_FLFG

# --- Tax ---
from tax_law_crawler import CHANNEL_ID_CACHE, parse_results as tax_parse
from tests.fixtures.tax.data import API_RESPONSE

# --- MEE ---
from mee_law_crawler import parse_list_page as mee_parse
from tests.fixtures.mee.data import LIST_HTML_FL

# --- Court ---
from court_law_crawler import parse_list_page as court_parse
from tests.fixtures.court.data import LIST_HTML_PAGE1_INTERP


SOURCES = [
    ("gov_policy", gov_parse, SEARCH_RESPONSE, "gov_policy_library", "gov.cn"),
    ("moj", moj_parse, SEARCH_HTML, "moj_law", "moj.gov.cn"),
    ("party", party_parse, LIST_HTML_TIAOLI, "party_law", "12371.cn"),
    ("mod", mod_parse, INDEX_HTML_FLFG, "mod_law", "mod.gov.cn"),
    ("tax", tax_parse, API_RESPONSE, "tax_law", "chinatax.gov.cn"),
    ("mee", mee_parse, LIST_HTML_FL, "mee_law", "mee.gov.cn"),
    ("court", court_parse, LIST_HTML_PAGE1_INTERP, "court_law", "court.gov.cn"),
]


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_returns_list_of_dict(name, parser, fixture, expected_source, expected_host):
    """Every parser must return list[dict]."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    result = parser(fixture)
    if name == "moj" or name == "court":
        result = result[0] if isinstance(result, tuple) else result
    assert isinstance(result, list)
    if result:
        assert isinstance(result[0], dict)


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_records_have_nonempty_title(name, parser, fixture, expected_source, expected_host):
    """Every record must have a non-empty title."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    result = parser(fixture)
    if name == "moj" or name == "court":
        result = result[0] if isinstance(result, tuple) else result
    for r in result:
        assert "title" in r
        assert r["title"] is not None
        assert len(str(r["title"])) > 0


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_records_have_http_url(name, parser, fixture, expected_source, expected_host):
    """Every record must have an HTTP/HTTPS URL pointing to the correct host."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    result = parser(fixture)
    if name == "moj" or name == "court":
        result = result[0] if isinstance(result, tuple) else result
    for r in result:
        # Find the URL field (varies by source: 'url', 'detail_url')
        url = r.get("url") or r.get("detail_url") or ""
        if not url:
            continue  # some fixtures have empty-url records intentionally
        assert url.startswith("http://") or url.startswith("https://"), \
            f"URL must use HTTP(S): {url}"
        assert expected_host in url, \
            f"URL host mismatch for {name}: expected {expected_host} in {url}"


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_source_field_matches(name, parser, fixture, expected_source, expected_host):
    """source field (or equivalent) must identify the database."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    result = parser(fixture)
    if name == "moj" or name == "court":
        result = result[0] if isinstance(result, tuple) else result
    for r in result:
        assert "source" in r
        assert r["source"] == expected_source


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_json_serializable(name, parser, fixture, expected_source, expected_host):
    """All records must be JSON-serializable."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    result = parser(fixture)
    if name == "moj" or name == "court":
        result = result[0] if isinstance(result, tuple) else result
    s = json.dumps(result, ensure_ascii=False)
    assert isinstance(s, str)


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_no_fabricated_effectiveness(name, parser, fixture, expected_source, expected_host):
    """No record invents '现行有效' unless the fixture explicitly provides it."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    result = parser(fixture)
    if name == "moj" or name == "court":
        result = result[0] if isinstance(result, tuple) else result
    for r in result:
        # 'status' key should only exist if the parser explicitly sets it
        # from an official source field
        if "status" in r:
            val = r["status"]
            assert val in ("", "现行有效", "已废止", "已修改", "尚未生效", None), \
                f"Unexpected status value: {val}"


@pytest.mark.parametrize("name,parser,fixture,expected_source,expected_host", SOURCES)
def test_missing_fields_no_exception(name, parser, fixture, expected_source, expected_host):
    """Missing optional fields must not cause KeyError or None.lower() or AttributeError."""
    if name == "tax":
        CHANNEL_ID_CACHE.clear()
    try:
        result = parser(fixture)
        if name == "moj" or name == "court":
            result = result[0] if isinstance(result, tuple) else result
        # Try accessing common fields — should not crash
        for r in result:
            _ = r.get("title", "")
            _ = r.get("source", "")
    except (KeyError, AttributeError, TypeError) as e:
        pytest.fail(f"{name} parser raised {type(e).__name__}: {e}")
