#!/usr/bin/env python3
"""
MCP server exposing cn-law-hub's legal-data search capabilities.

Single MCP server process exposing multiple tools.  This is an *additional*
access path — the skill (SKILL.md) and the CLI scripts remain the primary way
to use the project; this module only reuses their internal functions.

Setup:
  pip install mcp
  python scripts/mcp_server.py        # stdio transport, waits for MCP client

Tools:
  search_laws      — unified search across 10 official data sources
  get_law_detail   — fetch a record's detail page by URL / id
  query_article    — query specific articles of an NPC law by bbbs id
  preview_law      — preview an NPC law's structure (articles / numbering)
  article_search   — search a keyword across articles of multiple laws
"""

import contextlib
import io
import sys
from pathlib import Path

# Ensure `scripts/` is importable so `from common import ...` resolves.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import article_search as article_search_mod  # noqa: E402  (module alias: keeps the tool name free)
import court_law_crawler  # noqa: E402
import download  # noqa: E402
import gov_policy_library  # noqa: E402
import gov_rules_crawler  # noqa: E402
import mee_law_crawler  # noqa: E402
import mod_law_crawler  # noqa: E402
import moj_law_crawler  # noqa: E402
import party_law_crawler  # noqa: E402
import tax_law_crawler  # noqa: E402
import treaty_crawler  # noqa: E402

from common import (  # noqa: E402
    is_article_line,
    match_article_query,
    split_into_articles,
)

mcp = MCPServer(
    name="cn-law-hub",
    title="cn-law-hub 法律数据检索",
    version="2.0",
    description="检索 10 个官方数据源的中国法律法规 / 政策 / 条约",
)

SOURCE_ENUM = "npc / gov_policy / moj / party / mod / tax / mee / court / gov_rules / treaty"
GOV_RULES_CATEGORIES = ["部门规章", "地方政府规章"]
TREATY_COLLECTIONS = ["全部", "双边", "多边"]


# ---------------------------------------------------------------------------
# Per-source search handlers (keyword, category, size) -> list[dict]
# ---------------------------------------------------------------------------


def _search_npc(keyword: str, category: str, size: int) -> list:
    data = download.search_laws(keyword, size=size)
    if data.get("code") != 200:
        return []
    return data.get("rows", [])


def _search_gov_policy(keyword: str, category: str, size: int) -> list:
    return gov_policy_library.search_collect(keyword, max_items=size)


def _search_moj(keyword: str, category: str, size: int) -> list:
    return moj_law_crawler.search_collect(keyword, max_items=size)


def _search_party(keyword: str, category: str, size: int) -> list:
    return party_law_crawler.search_collect(keyword, category=category, max_items=size)


def _search_mod(keyword: str, category: str, size: int) -> list:
    return mod_law_crawler.search_collect(keyword, category=category, max_items=size)


def _search_mee(keyword: str, category: str, size: int) -> list:
    return mee_law_crawler.search_collect(keyword, category=category, max_items=size)


def _search_court(keyword: str, category: str, size: int) -> list:
    return court_law_crawler.search_collect(keyword, category=category, max_items=size)


def _search_tax(keyword: str, category: str, size: int) -> list:
    session = tax_law_crawler.create_session()
    return tax_law_crawler.search_collect(session, keyword, category=category, max_items=size)


_athena_auth = None


def _get_athena_auth():
    """Lazily build + discover the gov.cn AthenaAuth (cached per process)."""
    global _athena_auth
    if _athena_auth is None:
        auth = gov_rules_crawler.AthenaAuth()
        auth.discover()
        _athena_auth = auth
    return _athena_auth


def _search_gov_rules(keyword: str, category: str, size: int) -> list:
    auth = _get_athena_auth()
    return gov_rules_crawler.search_category(auth, category, keyword=keyword, max_items=size)


def _search_treaty(keyword: str, category: str, size: int) -> list:
    return treaty_crawler.search_collection(category, keyword=keyword, max_items=size)


_SEARCH_ROUTER = {
    "npc": _search_npc,
    "gov_policy": _search_gov_policy,
    "moj": _search_moj,
    "party": _search_party,
    "mod": _search_mod,
    "tax": _search_tax,
    "mee": _search_mee,
    "court": _search_court,
    "gov_rules": _search_gov_rules,
    "treaty": _search_treaty,
}

# Sources whose search requires a category (used as category_name / collection_name).
_REQUIRED_CATEGORY = {
    "gov_rules": GOV_RULES_CATEGORIES,
    "treaty": TREATY_COLLECTIONS,
}

_DETAIL_ROUTER = {
    "npc": lambda url: download.fetch_detail(url),
    "gov_policy": lambda url: gov_policy_library.fetch_detail_page(url),
    "moj": lambda url: moj_law_crawler.fetch_detail(url),
    "party": lambda url: party_law_crawler.fetch_detail(url),
    "mod": lambda url: mod_law_crawler.fetch_detail(url),
    "tax": lambda url: tax_law_crawler.fetch_detail(url),
    "mee": lambda url: mee_law_crawler.fetch_detail(url),
    "court": lambda url: court_law_crawler.fetch_detail(url),
    "gov_rules": lambda url: gov_rules_crawler.parse_detail_page(url),
    "treaty": lambda url: treaty_crawler.parse_detail(url),
}


def _with_source(records: list, source: str) -> list:
    out = []
    for r in records:
        item = dict(r) if isinstance(r, dict) else {"value": r}
        item["source"] = source
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
def search_laws(source: str, keyword: str = "", category: str = "", size: int = 20) -> dict:
    """Search Chinese laws / regulations / policies from one official source.

    Args:
        source: Data source. One of:
            npc 国家法律法规库 · gov_policy 政策文件库 · moj 司法部 · party 党内法规 ·
            mod 国防部 · tax 财政部 · mee 生态环境部 · court 人民法院 · gov_rules 行政法规 ·
            treaty 条约。
        keyword: Search keyword.
        category: Category filter. REQUIRED for `gov_rules` (部门规章 / 地方政府规章)
            and `treaty` (全部 / 双边 / 多边); optional for party/mod/tax/mee/court.
        size: Max results to return (default 20).

    Returns:
        {"source", "records", "count"} — each record tagged with its source.
    """
    if source not in _SEARCH_ROUTER:
        return {
            "source": source,
            "records": [],
            "count": 0,
            "error": f"Unknown source '{source}'. Expected one of: {SOURCE_ENUM}",
        }
    if source in _REQUIRED_CATEGORY and not category:
        return {
            "source": source,
            "records": [],
            "count": 0,
            "error": f"source='{source}' requires a 'category'. Options: {_REQUIRED_CATEGORY[source]}",
        }
    try:
        records = _SEARCH_ROUTER[source](keyword, category, size)
    except Exception as e:  # surface errors instead of crashing the server
        return {"source": source, "records": [], "count": 0, "error": f"{type(e).__name__}: {e}"}
    records = _with_source(records, source)
    return {"source": source, "records": records, "count": len(records)}


@mcp.tool()
def get_law_detail(source: str, url: str) -> dict:
    """Fetch the detail page of a record (metadata / full text) by its URL (or npc bbbs id).

    Args:
        source: One of {SOURCE_ENUM}.
        url: The record's detail URL — or, for source 'npc', the bbbs id.
    """
    if source not in _DETAIL_ROUTER:
        return {"source": source, "error": f"Unknown source '{source}'. Expected one of: {SOURCE_ENUM}"}
    try:
        detail = _DETAIL_ROUTER[source](url)
    except Exception as e:
        return {"source": source, "error": f"{type(e).__name__}: {e}"}
    return {"source": source, "detail": detail}


@mcp.tool()
def query_article(bbbs_id: str, query: str = None, grep: str = None) -> dict:
    """Query specific articles of a law from the NPC national database (flk.npc.gov.cn).

    Provide either `query` (an article number, e.g. "第三十八条" / "第38条") or
    `grep` (a keyword to search within article text).  `bbbs_id` comes from
    search_laws(source='npc').

    Returns:
        {"title", "bbbs", "query", "grep", "count", "results": [{"article_num", "text"}]}
    """
    if not query and not grep:
        return {"error": "Provide either 'query' (article number, e.g. 第三十八条) or 'grep' (keyword)"}
    try:
        paragraphs, info = download._download_docx_text(bbbs_id)
        articles = split_into_articles(paragraphs)
        results = []
        if grep:
            results = [(n, t) for n, t in articles if grep in t]
        elif query:
            results = [(n, t) for n, t in articles if match_article_query(query, n)]
            if not results:
                results = [(n, t) for n, t in articles if query in t[: len(query) + 15]]
        return {
            "title": info.get("title"),
            "bbbs": bbbs_id,
            "query": query,
            "grep": grep,
            "count": len(results),
            "results": [{"article_num": n, "text": t} for n, t in results],
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool()
def preview_law(bbbs_id: str) -> dict:
    """Preview the structure of an NPC law: title, article count, numbering pattern,
    and the first 20 articles.  `bbbs_id` comes from search_laws(source='npc')."""
    try:
        raw = download.fetch_detail(bbbs_id)
        content_tree = (raw or {}).get("data", {}).get("content", {})
        detected = download._detect_numbering_patterns(content_tree)
        paragraphs, info = download._download_docx_text(bbbs_id)
        articles = split_into_articles(paragraphs)
        article_count = len([a for a in articles if is_article_line(a[0])])
        preview = [
            {
                "article_num": num,
                "text": text.replace("\n", " ")[:70],
                "is_article": is_article_line(num),
            }
            for num, text in articles[:20]
        ]
        return {
            "title": info.get("title"),
            "bbbs": bbbs_id,
            "category": info.get("category"),
            "authority": info.get("authority"),
            "publish_date": info.get("publish_date"),
            "status_str": info.get("status_str"),
            "total_paragraphs": len(paragraphs),
            "article_count": article_count,
            "numbering": detected["primary"],
            "sample_titles": detected["sample_titles"][:3],
            "preview_count": len(preview),
            "preview": preview,
            "truncated": len(articles) > 20,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@mcp.tool()
def article_search(keyword: str, law_keyword: str = None, max_laws: int = 5, context: int = 0) -> dict:
    """Search a keyword across articles of multiple laws from the NPC database.

    Args:
        keyword: The article-text keyword to find.
        law_keyword: Narrow the law titles/full-text search (defaults to keyword).
        max_laws: How many laws to scan (default 5).
        context: Include N surrounding articles around each match (default 0).

    Returns:
        {"keyword", "count", "laws": [{title, bbbs, status_str, total_articles,
         matched_articles, articles: [{article_num, text, is_match}]}]}
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            matches = article_search_mod.search_articles(
                keyword, law_keyword=law_keyword, max_laws=max_laws, context=context
            )
    except Exception as e:
        return {"keyword": keyword, "count": 0, "laws": [], "error": f"{type(e).__name__}: {e}"}
    return {"keyword": keyword, "count": len(matches), "laws": matches}


if __name__ == "__main__":
    mcp.run()
