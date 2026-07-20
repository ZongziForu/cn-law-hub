#!/usr/bin/env python3
"""
Download regulations from the State Council Rules Database (国家规章库).

Usage:
  python gov_rules_crawler.py --search "管理办法" --categories 部门规章 --size 20
  python gov_rules_crawler.py --categories 地方政府规章 --size 50 --download
  python gov_rules_crawler.py --info "https://www.gov.cn/zhengce/xxgk/gjgzk/..."
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from common import (
    DEFAULT_USER_AGENT,
    _CacheManager,
    clean_text,
    create_crawler_headers,
    ensure_dir,
    extract_year,
    get_cache,
    http_request,
    init_limiter,
    render_markdown_report,
    sanitize_filename,
    setup_logger,
    unique_path,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except ImportError:
    serialization = None
    padding = None

INDEX_URL = "https://www.gov.cn/zhengce/xxgk/gjgzk/index.htm?searchWord="
QUERY_ENDPOINT_PATH = "/athena/forward/BD8730CDDA12515E2D9E1B21AA11C0D6"
CATEGORY_MAP = {"部门规章": "部门规章", "地方政府规章": "地方政府规章"}
DEFAULT_CATEGORIES = ["部门规章", "地方政府规章"]
HEADERS = create_crawler_headers()

_cache = get_cache("npc-law-db-govrules")

# ---------------------------------------------------------------------------
# Athena auth discovery (RSA key extraction from frontend JS)
# ---------------------------------------------------------------------------


class AthenaAuth:
    def __init__(self):
        self.base_url = ""
        self.app_key = ""
        self.app_name = ""

    def build_key(self, public_key_b64: str, seed: str) -> str:
        if serialization is None or padding is None:
            raise RuntimeError("pip install cryptography")
        pem = (
            f"-----BEGIN PUBLIC KEY-----\n{public_key_b64}\n-----END PUBLIC KEY-----\n"
        ).encode("ascii")
        public_key = serialization.load_pem_public_key(pem)
        encrypted = public_key.encrypt(seed.encode("utf-8"), padding.PKCS1v15())
        return quote(base64.b64encode(encrypted).decode("ascii"), safe="")

    def discover(self) -> None:
        resp = http_request("GET", INDEX_URL, headers=HEADERS)
        resp.encoding = "utf-8"
        html = resp.text
        script_match = re.search(r'<script src="(index\.js\?[^"]+)"></script>', html)
        if not script_match:
            raise RuntimeError("Cannot find index.js")
        script_url = urljoin(INDEX_URL, script_match.group(1))
        script_text = http_request("GET", script_url).text
        auth_match = re.search(
            r'var s="(?P<base>https://[^"]+)",o=encodeURIComponent\(a\("(?P<pub>[^"]+)","(?P<seed>[^"]+)"\)\),c=encodeURIComponent\("(?P<name>[^"]+)"\)',
            script_text,
        )
        if not auth_match:
            raise RuntimeError("Cannot extract auth params from JS")
        self.base_url = auth_match.group("base")
        self.app_key = self.build_key(auth_match.group("pub"), auth_match.group("seed"))
        self.app_name = quote(auth_match.group("name"), safe="")

    def headers(self) -> dict:
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://www.gov.cn/",
            "athenaappname": self.app_name,
            "athenaappkey": self.app_key,
        }


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------


def search_page(
    auth: AthenaAuth,
    category_name: str,
    page_no: int,
    page_size: int = 500,
    keyword: str = "",
    timeout: int = 30,
) -> dict:
    cache_key = _cache._key(
        "search_page", category_name, str(page_no), str(page_size), keyword or ""
    )
    cached = _cache.get(cache_key, max_age=3600)
    if cached:
        return cached

    title_search: dict = {"fieldName": "f_202321360426", "withHighLight": True}
    if keyword:
        title_search["searchWord"] = keyword
        title_search["searchType"] = "TERM"

    payload = {
        "code": "18258ab0ac9",
        "preference": None,
        "searchFields": [
            {
                "fieldName": "f_202321807875",
                "searchWord": category_name,
                "searchType": "TERM",
                "withHighLight": True,
            },
            title_search,
            {"fieldName": "f_202321758948", "withHighLight": True},
            {
                "fieldName": "f_202321423473",
                "searchType": "TERM",
                "withHighLight": True,
            },
            {"fieldName": "f_202321159816", "searchWord": "", "searchType": "TERM"},
            {"fieldName": "f_20232380533", "searchType": "TERM", "withHighLight": True},
            {
                "fieldName": "f_202328191239",
                "withHighLight": True,
                "searchType": "TERM",
            },
            {
                "fieldName": "f_20221110222856",
                "withHighLight": True,
                "searchType": "TERM",
            },
        ],
        "sorts": [{}, {"sortField": "f_202321915922", "sortOrder": "DESC"}],
        "resultFields": [
            "f_202355832506",
            "f_20232124962",
            "f_202321124775",
            "f_202321159816",
            "f_202321360426",
            "f_202321423473",
            "f_202321758948",
            "f_202321807875",
            "f_202321864401",
            "f_202321915922",
            "f_202323394765",
            "f_202328191239",
            "f_202344311304",
            "f_202355832506",
            "f_2023425676953",
            "f_2023425808265",
            "f_202321136868",
            "f_20232380533",
            "f_20232151076",
            "doc_pub_url",
        ],
        "trackTotalHits": "true",
        "tableName": "t_1860c735d31",
        "pageSize": page_size,
        "pageNo": page_no,
        "granularity": "ALL",
    }
    resp = http_request(
        "POST",
        f"{auth.base_url}{QUERY_ENDPOINT_PATH}",
        json=payload,
        headers=auth.headers(),
        timeout=timeout,
    )
    data = resp.json()
    if data["resultCode"]["code"] != 200:
        raise RuntimeError(f"Search failed: {data['resultCode']}")
    result = data["result"]["data"]
    _cache.set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Detail page parsing
# ---------------------------------------------------------------------------


def parse_detail_page(detail_url: str, timeout: int = 30) -> dict:
    cache_key = _cache._key("detail_html", detail_url)
    cached = _cache.get(cache_key, max_age=86400)
    if cached:
        return cached
    resp = http_request(
        "GET",
        detail_url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html",
        },
        timeout=timeout,
    )
    resp.encoding = "utf-8"
    html = resp.text
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        content_node = soup.select_one(".pages_content")
        text_content = clean_text(
            content_node.get_text("\n", strip=True) if content_node else ""
        )
        attachments = []
        for anchor in soup.select(
            'a[href][appendix="true"], a[href][data-appendix="true"]'
        ):
            href = anchor.get("href")
            if not href:
                continue
            attachments.append(
                {
                    "title": clean_text(
                        anchor.get_text(" ", strip=True) or anchor.get("title") or ""
                    ),
                    "url": urljoin(detail_url, href),
                }
            )
    else:
        text_content = ""
        attachments = []
    result = {"html": html, "text": text_content, "attachments": attachments}
    _cache.set(cache_key, result)
    return result


def download_file(url: str, path: Path, timeout: int = 60) -> Path:
    resp = http_request(
        "GET", url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=timeout
    )
    final_path = unique_path(path)
    with final_path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 64):
            if chunk:
                fh.write(chunk)
    return final_path


# ---------------------------------------------------------------------------
# Search and collect
# ---------------------------------------------------------------------------


def search_category(
    auth: AthenaAuth,
    category_name: str,
    keyword: str = "",
    max_items: int = None,
    max_pages: int = None,
    page_size: int = 500,
    timeout: int = 30,
) -> list[dict]:
    records = []
    page_no = 1
    total = None
    page_count = None
    while True:
        if max_pages is not None and page_no > max_pages:
            break
            data = search_page(
                auth,
                category_name,
                page_no,
                page_size=page_size,
                keyword=keyword,
                timeout=timeout,
            )
        pager = data["pager"]
        items = data["list"]
        if total is None:
            total = pager["total"]
            page_count = pager["pageCount"]
            print(f"  Total: {total} records, {page_count} pages", file=sys.stderr)
        if not items:
            break
        for item in items:
            title = clean_text(item.get("f_202321360426"))
            detail_url = clean_text(item.get("doc_pub_url"))
            if keyword and keyword.lower() not in title.lower():
                continue
            record = {
                "source": "gov_rules",
                "category": category_name,
                "title": title,
                "issuer": clean_text(item.get("f_202323394765")),
                "law_type": clean_text(item.get("f_202321807875")),
                "publish_text": clean_text(item.get("f_202344311304")),
                "publish_time": clean_text(item.get("f_202321915922")),
                "org_names": clean_text(item.get("f_202328191239")),
                "detail_url": detail_url,
                "body_excerpt": clean_text(item.get("f_202321758948"))[:300],
                "downloaded_text": "",
                "downloaded_html": "",
                "attachment_files": [],
            }
            records.append(record)
            if max_items is not None and len(records) >= max_items:
                break
        if max_items is not None and len(records) >= max_items:
            break
        if page_no >= page_count:
            break
        page_no += 1
    return records


# ---------------------------------------------------------------------------
# Output / report
# ---------------------------------------------------------------------------


def save_results(
    records: list[dict],
    output_dir: Path,
    category_name: str,
    download_files: bool = True,
) -> Path:
    category_root = ensure_dir(
        output_dir / sanitize_filename(category_name, category_name)
    )
    files_root = ensure_dir(category_root / "files")

    if download_files:
        for record in records:
            if not record.get("detail_url"):
                continue
            try:
                record_dir = ensure_dir(
                    files_root / sanitize_filename(record["title"], "rule")
                )
                detail = parse_detail_page(record["detail_url"])
                html_path = record_dir / "page.html"
                txt_path = record_dir / "page.txt"
                html_path.write_text(detail["html"], encoding="utf-8")
                txt_path.write_text(detail["text"], encoding="utf-8")
                record["downloaded_html"] = str(html_path.relative_to(category_root))
                record["downloaded_text"] = str(txt_path.relative_to(category_root))
                attachment_files = []
                for att in detail["attachments"]:
                    try:
                        ext = Path(urlparse(att["url"]).path).suffix or ""
                        filename = sanitize_filename(att["title"], "attachment")
                        saved_path = download_file(
                            att["url"], record_dir / f"{filename}{ext}"
                        )
                        attachment_files.append(
                            str(saved_path.relative_to(category_root))
                        )
                    except Exception:
                        pass
                record["attachment_files"] = attachment_files
            except Exception:
                pass

    write_jsonl(category_root / "metadata.jsonl", records)
    write_csv(category_root / "metadata.csv", records)

    issuer_counts = {}
    year_counts = {}
    for row in records:
        issuer = row.get("issuer", "")
        if issuer:
            issuer_counts[issuer] = issuer_counts.get(issuer, 0) + 1
        year = extract_year(row.get("publish_time", ""))
        if year != "未知":
            year_counts[year] = year_counts.get(year, 0) + 1

    top_issuers = [
        {"name": k, "count": v}
        for k, v in sorted(issuer_counts.items(), key=lambda x: -x[1])[:15]
    ]
    stats = {
        "source": "gov_rules",
        "category": category_name,
        "record_count": len(records),
        "top_issuers": top_issuers,
        "publish_year_distribution": dict(sorted(year_counts.items())),
    }
    write_json(category_root / "stats_report.json", stats)

    md = render_markdown_report(
        f"国家规章库统计报告 - {category_name}",
        [
            ("概览", {"category": category_name, "record_count": len(records)}),
            ("发文机关 Top 15", top_issuers),
            ("发布年份分布", stats["publish_year_distribution"]),
        ],
    )
    write_text(category_root / "stats_report.md", md)
    write_json(
        category_root / "summary.json",
        {"source": "gov_rules", "category": category_name, "count": len(records)},
    )
    return category_root


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="国家规章库爬虫")
    parser.add_argument("--search", default="", help="Search keyword")
    parser.add_argument(
        "--categories", nargs="*", default=None, choices=list(CATEGORY_MAP.keys())
    )
    parser.add_argument("--size", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--info", default=None)
    parser.add_argument("--output", "-o", default="./gov_rules_output")
    parser.add_argument(
        "--rate-limit", choices=["auto", "off", "fixed", "adaptive"], default="auto"
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--cache-stats", action="store_true")
    parser.add_argument("--cache-clear", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if BeautifulSoup is None:
        print("Error: pip install beautifulsoup4", file=sys.stderr)
        return 1
    if serialization is None or padding is None:
        print("Error: pip install cryptography", file=sys.stderr)
        return 1

    output_dir = Path(args.output).expanduser().resolve()
    logger = setup_logger(output_dir, name="gov_rules_crawler")

    if args.no_cache:
        global _cache
        _cache = _CacheManager(enabled=False, namespace="npc-law-db-govrules")
    if args.cache_stats:
        stats = _cache.stats()
        print(f"Cache: {stats['entries']} entries, {stats['size_kb']} KB")
        print(f"Location: {_cache.dir}")
        return 0
    if args.cache_clear:
        _cache.clear()
        print("Cache cleared.")
        return 0

    if args.info:
        detail = parse_detail_page(args.info)
        print(
            json.dumps(
                {
                    "text_preview": detail["text"][:2000],
                    "attachments": detail["attachments"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    limiter, forced = init_limiter(args.rate_limit)
    categories = args.categories or DEFAULT_CATEGORIES
    limiter.init_for_task(
        estimated_requests=(args.size or 100) * len(categories), forced_mode=forced
    )

    download_files = args.download and not args.no_download
    logger.info(
        "Start: categories=%s, keyword=%s, download=%s",
        categories,
        args.search,
        download_files,
    )

    print("Discovering API auth...", file=sys.stderr)
    auth = AthenaAuth()
    try:
        auth.discover()
        print(f"  Auth OK: {auth.base_url}", file=sys.stderr)
    except Exception as e:
        logger.error("Auth failed: %s", e)
        return 1

    results = []
    for category in categories:
        logger.info("Category: %s", category)
        try:
            records = search_category(
                auth,
                category,
                keyword=args.search,
                max_items=args.size,
                max_pages=args.max_pages,
                page_size=args.page_size,
                timeout=args.timeout,
            )
            category_root = save_results(records, output_dir, category, download_files)
            results.append(
                {
                    "category": category,
                    "count": len(records),
                    "path": str(category_root),
                }
            )
        except Exception as e:
            logger.error("Failed: %s", e)
            results.append({"category": category, "count": 0, "error": str(e)})

    summary = {
        "source": "gov_rules",
        "categories": results,
        "total": sum(r.get("count", 0) for r in results),
    }
    write_json(output_dir / "summary.json", summary)
    limiter.print_summary()
    logger.info("All done: %s", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
