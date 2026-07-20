#!/usr/bin/env python3
"""
Download laws/regulations from China's National Laws and Regulations Database.

Modes:
  Search (title):   python download.py --search "出租车" [--size 20]
  Search (content): python download.py --search "违约金" --range content [--size 20]
  Search URLs:      python download.py --search "出租车" --urls-only [--format docx|pdf] [--size 100]
  Detail:           python download.py --info <bbbs_id>
  Download:         python download.py --download <bbbs_id> [--format docx|pdf] [output]
  Preview:          python download.py --preview <bbbs_id>
  Article:          python download.py --article <bbbs_id> "第三十八条"
  Article grep:     python download.py --article <bbbs_id> --grep "经济补偿"
  Direct URL:       python download.py <file_url> [output]

Rate Limiting:
  --rate-limit auto      Auto-select based on task size (default)
  --rate-limit off       No throttling (small tasks)
  --rate-limit fixed     Fixed ~5 req/s (medium tasks)
  --rate-limit adaptive  Adaptive speed (large tasks)
  --rps N                Fixed N requests per second (e.g., --rps 3)

Environment:
  SSL verification is disabled by default. To enable: export NPC_LAW_VERIFY_SSL=1
  Cache is enabled by default. To disable: export NPC_LAW_NO_CACHE=1

Examples:
  python download.py --search "出租车"
  python download.py --search "违约金" --range content --size 50
  python download.py --search "出租车" --urls-only --size 100 --rate-limit adaptive
  python download.py --info "2c909fdd678bf17901678bf73ebd064f"
  python download.py --download "ff80808172b5f24f0172d9f04f0910af" --format docx out.doc
  python download.py --preview "2c909fdd678bf17901678bf74d7106b3"
  python download.py --article "2c909fdd678bf17901678bf74d7106b3" "第三十八条"
"""

import argparse
import json
import os
import re
import sys

from common import (
    DEFAULT_USER_AGENT,
    _CacheManager,
    _RateLimitConfig,
    _RateLimitMode,
    _SmartRateLimiter,
    get_cache,
    http_request,
    init_limiter,
)
from common import (
    extract_paragraphs_from_docx as _extract_paragraphs_from_docx,
)
from common import (
    is_article_line as _is_article_line,
)
from common import (
    match_article_query as _match_article_query,
)
from common import (
    split_into_articles as _split_into_articles,
)

BASE_URL = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Referer": "https://flk.npc.gov.cn/",
    "Accept": "application/json, text/plain, */*",
}

_SXX_MAP = {1: "已废止", 2: "已修改", 3: "现行有效", 4: "尚未生效"}


def sxx_to_str(code: int) -> str:
    return _SXX_MAP.get(code, f"未知({code})")


# Backward-compatible re-exports for tests and article_search.py
_cache = get_cache("npc-law-db")


def _request(method, url, **kwargs):
    """Thin wrapper so tests can mock download._request while using shared http_request."""
    kwargs.setdefault("headers", HEADERS)
    return http_request(method, url, **kwargs)


# ---------------------------------------------------------------------------
# Core API helpers
# ---------------------------------------------------------------------------


def search_laws(
    keyword: str,
    page: int = 1,
    size: int = 20,
    search_range: int = 1,
    search_type: int = 2,
    status_filter: list[int] | None = None,
) -> dict:
    """Search laws. search_range: 1=title, 2=content."""
    cache_key = _cache._key(
        "search",
        keyword,
        str(page),
        str(size),
        str(search_range),
        str(search_type),
        "".join(str(s) for s in (status_filter or [])),
    )
    cached = _cache.get(cache_key, max_age=3600)
    if cached:
        return cached

    payload = {
        "searchRange": search_range,
        "sxrq": [],
        "gbrq": [],
        "sxx": status_filter or [],
        "searchType": search_type,
        "xgzlSearch": False,
        "searchContent": keyword,
        "orderByParam": {"order": "-1", "sort": ""},
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "gbrqYear": [],
        "pageNum": page,
        "pageSize": size,
    }
    resp = _request(
        "POST",
        f"{BASE_URL}/law-search/search/list",
        json=payload,
        headers={
            **HEADERS,
            "Referer": f"{BASE_URL}/search",
            "Content-Type": "application/json",
        },
    )
    data = resp.json()
    _cache.set(cache_key, data)
    return data


def fetch_detail(bbbs_id: str) -> dict:
    cache_key = _cache._key("detail", bbbs_id)
    cached = _cache.get(cache_key, max_age=86400)
    if cached:
        return cached
    try:
        resp = _request(
            "GET", f"{BASE_URL}/law-search/search/flfgDetails", params={"bbbs": bbbs_id}
        )
        data = resp.json() if resp.status_code == 200 else {}
        _cache.set(cache_key, data)
        return data
    except Exception as e:
        print(f"Error fetching detail: {e}", file=sys.stderr)
        return {}


def parse_detail(data: dict) -> dict:
    if not data or data.get("code") != 200:
        return {}
    d = data.get("data", {})
    oss = d.get("ossFile", {}) or {}
    sxx_code = d.get("sxx", 0)
    return {
        "bbbs": d.get("bbbs", ""),
        "title": d.get("title", "Unknown"),
        "category": d.get("flxz", ""),
        "authority": d.get("zdjgName", ""),
        "publish_date": d.get("gbrq", ""),
        "effective_date": d.get("sxrq", ""),
        "status_code": sxx_code,
        "status_str": sxx_to_str(sxx_code),
        "word_url": f"{BASE_URL}/{oss['ossWordPath']}"
        if oss.get("ossWordPath")
        else None,
        "pdf_url": f"{BASE_URL}/{oss['ossPdfPath']}" if oss.get("ossPdfPath") else None,
        "word_ofd_url": f"{BASE_URL}/{oss['ossWordOfdPath']}"
        if oss.get("ossWordOfdPath")
        else None,
        "pdf_ofd_url": f"{BASE_URL}/{oss['ossPdfOfdPath']}"
        if oss.get("ossPdfOfdPath")
        else None,
    }


def get_download_url(bbbs_id: str, fmt: str = "docx") -> str:
    resp = _request(
        "GET",
        f"{BASE_URL}/law-search/download/pc",
        params={"format": fmt, "bbbs": bbbs_id},
        headers={**HEADERS, "Referer": f"{BASE_URL}/detail?id={bbbs_id}"},
    )
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"Download API error: {data.get('msg')}")
    url = data.get("data", {}).get("url")
    if not url:
        raise RuntimeError(f"No download URL for format={fmt}")
    return url


def download_file(url: str, output_path: str | None = None) -> str:
    resp = _request("GET", url)
    resp.raise_for_status()
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct and len(resp.content) < 5000:
        raise RuntimeError("Server returned HTML instead of file")
    if not output_path:
        cd = resp.headers.get("Content-Disposition", "")
        m = re.search(r'filename="?([^"]+)"?', cd)
        output_path = m.group(1) if m else url.split("/")[-1].split("?")[0]
    assert output_path is not None  # guaranteed by logic above
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(resp.content)
    print(f"Downloaded: {output_path} ({len(resp.content)} bytes)")
    return output_path


def print_detail(info: dict):
    if not info:
        print("Failed to fetch detail")
        return
    print(f"Title: {info['title']}")
    print(f"Category: {info['category']}")
    print(f"Authority: {info['authority']}")
    print(f"Publish Date: {info['publish_date']}")
    print(f"Effective Date: {info['effective_date']}")
    print(f"Status: {info['status_str']} (code={info['status_code']})")
    print(f"BBBS: {info['bbbs']}")
    print("\nDownload URLs:")
    for key in ("word_url", "pdf_url", "word_ofd_url", "pdf_ofd_url"):
        if info.get(key):
            print(f"  {key}: {info[key]}")


def print_search_results(data: dict):
    if data.get("code") != 200:
        print(f"Search failed: {data.get('msg')}")
        return
    rows = data.get("rows", [])
    total = data.get("total", 0)
    print(f"Total: {total} | Returned: {len(rows)}")
    for row in rows:
        title = re.sub(r"<[^>]+>", "", row.get("title", ""))
        sxx = row.get("sxx", 0)
        print(f"- {title}")
        print(f"  bbbs: {row.get('bbbs')} | status: {sxx_to_str(sxx)}")
        print(f"  category: {row.get('flxz')} | authority: {row.get('zdjgName')}")
        print(f"  publish: {row.get('gbrq')}")


def collect_search_urls(data: dict, fmt: str = "docx") -> list:
    results = []
    rows = data.get("rows", []) if data.get("code") == 200 else []
    for row in rows:
        bbbs = row.get("bbbs")
        item = {
            "bbbs": bbbs,
            "title": re.sub(r"<[^>]+>", "", row.get("title", "")),
            "category": row.get("flxz"),
            "authority": row.get("zdjgName"),
            "publish_date": row.get("gbrq"),
            "effective_date": row.get("sxrq"),
            "status_code": row.get("sxx"),
            "status_str": sxx_to_str(row.get("sxx", 0)),
            "format": fmt,
            "url": None,
            "error": None,
        }
        try:
            item["url"] = get_download_url(bbbs, fmt)
        except Exception as e:
            item["error"] = str(e)
        results.append(item)
    return results


# ---------------------------------------------------------------------------
# DOCX / article helpers
# ---------------------------------------------------------------------------


def _detect_numbering_patterns(content_tree: dict) -> dict:
    patterns = {
        "primary": "chinese",
        "has_chinese": False,
        "has_arabic": False,
        "sample_titles": [],
    }
    if not content_tree:
        return patterns

    def walk(node):
        if not node:
            return
        title = node.get("title", "")
        if re.match(r"^第[一二三四五六七八九十百千万零]+条", title):
            patterns["has_chinese"] = True
            if len(patterns["sample_titles"]) < 5:
                patterns["sample_titles"].append(title)
        elif re.match(r"^第\d+条", title):
            patterns["has_arabic"] = True
            if len(patterns["sample_titles"]) < 5:
                patterns["sample_titles"].append(title)
        for child in node.get("children", []):
            walk(child)

    walk(content_tree)
    if patterns["has_arabic"] and not patterns["has_chinese"]:
        patterns["primary"] = "arabic"
    elif patterns["has_arabic"] and patterns["has_chinese"]:
        patterns["primary"] = "mixed"
    return patterns


def _download_docx_text(bbbs_id: str) -> tuple:
    """Download DOCX (or .doc) and extract paragraphs + metadata. Uses cache."""
    raw = fetch_detail(bbbs_id)
    info = parse_detail(raw)
    if not info:
        raise RuntimeError(f"Cannot fetch detail for {bbbs_id}")
    docx_key = _cache._key("docx", bbbs_id)
    docx_bytes = _cache.get_file(docx_key)
    if docx_bytes is None:
        url = get_download_url(bbbs_id, "docx")
        resp = _request("GET", url)
        ct = resp.headers.get("Content-Type", "")
        if "text/html" in ct and len(resp.content) < 5000:
            raise RuntimeError("Server returned HTML instead of DOCX")
        docx_bytes = resp.content
        _cache.set_file(docx_key, docx_bytes)
    paragraphs = _extract_paragraphs_from_docx(docx_bytes)
    return paragraphs, info


def preview_law(bbbs_id: str):
    raw = fetch_detail(bbbs_id)
    content_tree = (raw or {}).get("data", {}).get("content", {})
    detected = _detect_numbering_patterns(content_tree)
    try:
        paragraphs, info = _download_docx_text(bbbs_id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    articles = _split_into_articles(paragraphs)
    article_count = len([a for a in articles if _is_article_line(a[0])])
    print(f"【{info['title']}】")
    print(f"Category: {info['category']} | Authority: {info['authority']}")
    print(f"Publish: {info['publish_date']} | Status: {info['status_str']}")
    print(f"Total paragraphs: {len(paragraphs)} | Articles: {article_count}")
    label_map = {
        "chinese": "中文数字 (如: 第一条)",
        "arabic": "阿拉伯数字 (如: 第1条)",
        "mixed": "混合",
    }
    print(
        f"Numbering: {label_map.get(detected['primary'], detected['primary'])} | "
        f"Samples: {', '.join(detected['sample_titles'][:3]) or 'N/A'}"
    )
    print()
    for num, text in articles[:20]:
        preview = text.replace("\n", " ")[:70]
        marker = "📄" if _is_article_line(num) else "📁"
        print(f"{marker} {preview}")
    if len(articles) > 20:
        print(f"... ({len(articles) - 20} more)")


def query_article(bbbs_id: str, query: str | None = None, grep: str | None = None):
    raw = fetch_detail(bbbs_id)
    content_tree = (raw or {}).get("data", {}).get("content", {})
    detected = _detect_numbering_patterns(content_tree)
    try:
        paragraphs, info_file = _download_docx_text(bbbs_id)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    articles = _split_into_articles(paragraphs)
    results = []
    if grep:
        for num, text in articles:
            if grep in text:
                results.append((num, text))
    elif query:
        for num, text in articles:
            if _match_article_query(query, num):
                results.append((num, text))
        if not results:
            for num, text in articles:
                if query in text[: len(query) + 15]:
                    results.append((num, text))
    else:
        print("Error: Use --article with query or --grep KEYWORD", file=sys.stderr)
        sys.exit(1)
    print(f"【{info_file['title']}】")
    if not results:
        print(f"No article found for: {grep or query}")
        if query and detected["sample_titles"]:
            print(f"\nThis law uses: {detected['sample_titles'][0]}")
            print("Tip: Use --preview to see all article numbers.")
        return
    for num, text in results:
        print()
        print("=" * 60)
        print(text)
    print(f"\nFound: {len(results)} article(s)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="download.py",
        description="Download laws/regulations from China's National Laws and Regulations Database.",
        epilog="Examples:\n"
        "  python download.py --search '出租车'\n"
        "  python download.py --search '违约金' --range content --size 50\n"
        "  python download.py --search '出租车' --urls-only --size 100 --rate-limit adaptive\n"
        "  python download.py --info 2c909fdd678bf17901678bf73ebd064f\n"
        "  python download.py --download ff80808172b5f24f0172d9f04f0910af --format docx out.doc\n"
        "  python download.py --preview 2c909fdd678bf17901678bf74d7106b3\n"
        "  python download.py --article 2c909fdd678bf17901678bf74d7106b3 '第三十八条'\n"
        "\nRate Limiting:\n"
        "  --rate-limit auto      Auto by task size (default: small=off, medium=fixed, large=adaptive)\n"
        "  --rate-limit off       No throttling\n"
        "  --rate-limit fixed     Fixed ~5 req/s\n"
        "  --rate-limit adaptive  Adaptive speed with 429 backoff\n"
        "  --rps N                Fixed N req/s (e.g., --rps 3)\n"
        "\nEnvironment:\n"
        "  NPC_LAW_VERIFY_SSL=1  Enable SSL verification (disabled by default)\n"
        "  NPC_LAW_NO_CACHE=1    Disable cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--search", metavar="KEYWORD", help="Search by keyword")
    parser.add_argument(
        "--range",
        choices=["title", "content"],
        default="title",
        help="Search range: title (default) or content (full text)",
    )
    parser.add_argument("--info", metavar="BBBS", help="Fetch detail/metadata")
    parser.add_argument("--download", metavar="BBBS", help="Download a file")
    parser.add_argument("--preview", metavar="BBBS", help="Preview law structure")
    parser.add_argument("--article", metavar="BBBS", help="Query specific article")
    parser.add_argument("--grep", metavar="KEYWORD", help="Search keyword in articles")
    parser.add_argument(
        "--page", type=int, default=1, help="Search page number (default: 1)"
    )
    parser.add_argument(
        "--size", type=int, default=20, help="Search page size (default: 20)"
    )
    parser.add_argument("--exact", action="store_true", help="Use exact title match")
    parser.add_argument(
        "--urls-only",
        action="store_true",
        help="Output signed URLs instead of downloading",
    )
    parser.add_argument(
        "--format",
        default="docx",
        choices=["docx", "pdf"],
        help="Download format (default: docx)",
    )
    parser.add_argument(
        "--status", help="Filter by status: 1=已废止,2=已修改,3=现行有效,4=尚未生效"
    )
    parser.add_argument(
        "--rate-limit", default="auto", help="Rate limit mode (auto/off/fixed/adaptive)"
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=None,
        help="Fixed requests per second (e.g., --rps 3), overrides --rate-limit",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    parser.add_argument("--cache-stats", action="store_true", help="Show cache stats")
    parser.add_argument("--cache-clear", action="store_true", help="Clear cache")
    parser.add_argument(
        "output", nargs="?", help="Output path for --download or direct URL mode"
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Initialize rate limiter
    limiter, forced_mode = init_limiter("auto")

    if args.rps is not None:
        cfg = _RateLimitConfig(fixed_rps=args.rps)
        limiter = _SmartRateLimiter(cfg)
        forced_mode = _RateLimitMode.FIXED
    else:
        rl = (args.rate_limit or "auto").lower().strip()
        if rl in ("auto", ""):
            forced_mode = None
        elif rl in ("off", "0", "no", "false", "none"):
            forced_mode = _RateLimitMode.OFF
        elif rl in ("fixed", "fix"):
            forced_mode = _RateLimitMode.FIXED
        elif rl in ("adaptive", "adapt"):
            forced_mode = _RateLimitMode.ADAPTIVE
        else:
            print(
                f"Warning: Unknown --rate-limit '{args.rate_limit}', using auto",
                file=sys.stderr,
            )

    estimated = _SmartRateLimiter.estimate_task_size(
        search=args.search,
        size=args.size,
        urls_only=args.urls_only,
        info=args.info,
        download=args.download,
        preview=args.preview,
        article=args.article,
    )
    mode = limiter.init_for_task(estimated, forced_mode=forced_mode)
    if mode != _RateLimitMode.OFF:
        print(
            f"[RateLimit] {estimated} requests estimated -> {limiter.mode_desc()}",
            file=sys.stderr,
        )

    # Cache management
    if args.no_cache:
        global _cache
        _cache = _CacheManager(enabled=False, namespace="npc-law-db")
    if args.cache_stats:
        stats = _cache.stats()
        print(f"Cache: {stats['entries']} entries, {stats['size_kb']} KB")
        print(f"Location: {_cache.dir}")
        sys.exit(0)
    if args.cache_clear:
        _cache.clear()
        print("Cache cleared.")
        sys.exit(0)

    status_filter = None
    if args.status:
        status_filter = [int(s.strip()) for s in args.status.split(",")]

    search_range = 2 if args.range == "content" else 1
    search_type = 1 if args.exact else 2

    # Execute command
    try:
        if not any([args.info, args.search, args.download, args.preview, args.article]):
            if not args.output:
                parser.print_help()
                sys.exit(1)
            if not args.output.startswith(("http://", "https://")):
                parser.error(
                    "Direct mode requires a URL starting with http:// or https://"
                )
            download_file(args.output, None)
            return

        if args.info:
            raw = fetch_detail(args.info)
            print_detail(parse_detail(raw))
        elif args.search:
            data = search_laws(
                args.search,
                page=args.page,
                size=args.size,
                search_range=search_range,
                search_type=search_type,
                status_filter=status_filter,
            )
            if args.urls_only:
                enriched = collect_search_urls(data, args.format)
                json.dump(enriched, sys.stdout, ensure_ascii=False, indent=2)
                print()
            else:
                print_search_results(data)
        elif args.download:
            url = get_download_url(args.download, args.format)
            download_file(url, args.output)
        elif args.preview:
            preview_law(args.preview)
        elif args.article:
            query = args.output if args.output else None
            query_article(args.article, query=query, grep=args.grep)
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        limiter.print_summary()


if __name__ == "__main__":
    main()
