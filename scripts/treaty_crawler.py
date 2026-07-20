#!/usr/bin/env python3
"""
Download treaties from the Ministry of Foreign Affairs Treaty Database.

Usage:
  python treaty_crawler.py --search "上海合作组织" --size 20
  python treaty_crawler.py --collections 双边 --size 50 --download
  python treaty_crawler.py --info "https://treaty.mfa.gov.cn/web/detail.jsp?treatyid=..."
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from common import (
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

BASE_URL = "https://treaty.mfa.gov.cn/web/"
COLLECTION_URLS = {
    "全部": "allinfos.jsp?nPageIndex_={page}",
    "双边": "shuangbian.jsp?nPageIndex_={page}",
    "多边": "duobian.jsp?nPageIndex_={page}",
}
DEFAULT_COLLECTIONS = ["全部", "双边", "多边"]
HEADERS = create_crawler_headers()

_cache = get_cache("npc-law-db-treaty")

# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------


def fetch_html(url: str, timeout: int = 30):
    cache_key = _cache._key("html", url)
    cached_html = _cache.get(cache_key, max_age=86400)
    if cached_html and BeautifulSoup is not None:
        return BeautifulSoup(cached_html, "html.parser")
    resp = http_request("GET", url, headers=HEADERS, timeout=timeout)
    resp.encoding = "utf-8"
    _cache.set(cache_key, resp.text)
    if BeautifulSoup is not None:
        return BeautifulSoup(resp.text, "html.parser")
    return resp.text


def parse_page_count(soup) -> int:
    if isinstance(soup, str):
        text = soup
    else:
        text = soup.get_text(" ", strip=True)
    match = re.search(r"当前:\s*\d+\s*/\s*(\d+)\s*页", text)
    return int(match.group(1)) if match else 1


def parse_list_page(soup) -> list[dict]:
    if isinstance(soup, str):
        return []
    items = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "detail" not in href:
            continue
        title = clean_text(anchor.get("title") or anchor.get_text(" ", strip=True))
        if not title:
            continue
        items.append({"title": title, "detail_url": urljoin(BASE_URL, href)})
    return items


def _normalize_label(s: str) -> str:
    return re.sub(r"\s+|[：:]", "", s)


def parse_detail(detail_url: str) -> dict:
    soup = fetch_html(detail_url)
    if isinstance(soup, str):
        return {
            "title": "",
            "detail_url": detail_url,
            "error": "BeautifulSoup not installed",
        }

    content = soup.select_one("div.neirong") or soup
    text = content.get_text("\n", strip=True)
    title_node = content.select_one("p.neirongp")
    title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
    if not title and soup.title:
        title = clean_text(soup.title.get_text(strip=True).split("_")[0])
    if not title:
        first_lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = first_lines[0] if first_lines else ""

    # Parse metadata table if present
    field_map = {
        _normalize_label(k): v
        for k, v in {
            "类别：": "category",
            "领域：": "domain",
            "我国签署时间：": "sign_date",
            "条约生效时间：": "effective_date",
            "对我国生效时间：": "effective_to_china",
            "保存机关：": "depositary",
            "签署地点：": "sign_place",
            "港澳情况：": "hong_kong_macau",
            "我国声明保留情况：": "statement_reservation",
            "其他：": "other_info",
            "条约通过时间：": "adoption_date",
            "我国批准/核准/接受/加入时间：": "ratification_date",
            "条约适用于": "applies_to",
        }.items()
    }

    fields = {v: "" for v in field_map.values()}
    table = content.select_one("table.tab_con_a")
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            # Table layout: [label, value, label, value]
            for i in range(0, len(cells) - 1, 2):
                label = _normalize_label(cells[i].get_text("\n", strip=True))
                value = clean_text(cells[i + 1].get_text(" ", strip=True))
                key = field_map.get(label)
                if key:
                    fields[key] = value

    preview_links = []
    pdf_index = 1
    if table:
        for anchor in table.find_all("a", href=True):
            href = anchor["href"]
            if not href.lower().endswith(".pdf"):
                continue
            label = clean_text(anchor.get_text(" ", strip=True))
            label = label or f"preview_{pdf_index}"
            pdf_index += 1
            preview_links.append({"label": label, "url": urljoin(detail_url, href)})

    return {
        "title": title,
        "detail_url": detail_url,
        "category": fields["category"],
        "domain": fields["domain"],
        "sign_date": fields["sign_date"],
        "effective_date": fields["effective_date"],
        "effective_to_china": fields["effective_to_china"],
        "depositary": fields["depositary"],
        "sign_place": fields["sign_place"],
        "hong_kong_macau": fields["hong_kong_macau"],
        "statement_reservation": fields["statement_reservation"],
        "other_info": fields["other_info"],
        "adoption_date": fields["adoption_date"],
        "ratification_date": fields["ratification_date"],
        "applies_to": fields["applies_to"],
        "preview_links": preview_links,
    }


def collection_page_url(collection_name: str, page: int) -> str:
    return urljoin(BASE_URL, COLLECTION_URLS[collection_name].format(page=page))


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def download_file(url: str, path: Path, timeout: int = 60) -> Path:
    resp = http_request("GET", url, headers=HEADERS, timeout=timeout)
    final_path = unique_path(path)
    with final_path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 64):
            if chunk:
                fh.write(chunk)
    return final_path


# ---------------------------------------------------------------------------
# Search and collect
# ---------------------------------------------------------------------------


def search_collection(
    collection_name: str,
    keyword: str = "",
    max_items: int = None,
    max_pages: int = None,
    timeout: int = 30,
) -> list[dict]:
    records = []
    first_page = fetch_html(collection_page_url(collection_name, 1), timeout=timeout)
    page_count = parse_page_count(first_page)
    print(f'Collection "{collection_name}": {page_count} pages total', file=sys.stderr)

    current_page = 1
    while True:
        if max_pages is not None and current_page > max_pages:
            break
        soup = (
            first_page
            if current_page == 1
            else fetch_html(
                collection_page_url(collection_name, current_page), timeout=timeout
            )
        )
        items = parse_list_page(soup)
        if not items:
            break
        for item in items:
            if keyword and keyword.lower() not in item["title"].lower():
                continue
            try:
                detail = parse_detail(item["detail_url"])
            except Exception as e:
                detail = {
                    "title": item["title"],
                    "detail_url": item["detail_url"],
                    "error": str(e),
                }
            record = {
                "source": "treaty",
                "collection": collection_name,
                **detail,
                "downloaded_files": [],
            }
            records.append(record)
            if max_items is not None and len(records) >= max_items:
                break
        if max_items is not None and len(records) >= max_items:
            break
        if current_page >= page_count:
            break
        current_page += 1
    return records


# ---------------------------------------------------------------------------
# Output / report
# ---------------------------------------------------------------------------


def save_results(
    records: list[dict],
    output_dir: Path,
    collection_name: str,
    download_files: bool = True,
) -> Path:
    collection_root = ensure_dir(
        output_dir / sanitize_filename(collection_name, collection_name)
    )
    files_root = ensure_dir(collection_root / "files")

    if download_files:
        for record in records:
            if not record.get("preview_links"):
                continue
            record_dir = ensure_dir(
                files_root
                / sanitize_filename(f"{record['title']}_{collection_name}", "treaty")
            )
            downloaded_files = []
            for idx, preview in enumerate(record["preview_links"], start=1):
                try:
                    ext = Path(preview["url"].split("?")[0]).suffix or ".pdf"
                    filename = sanitize_filename(
                        f"{idx:02d}_{preview['label']}{ext}", f"{idx:02d}{ext}"
                    )
                    saved_path = download_file(preview["url"], record_dir / filename)
                    downloaded_files.append(
                        str(saved_path.relative_to(collection_root))
                    )
                except Exception:
                    pass
            record["downloaded_files"] = downloaded_files

    write_jsonl(collection_root / "metadata.jsonl", records)
    write_csv(collection_root / "metadata.csv", records)

    domain_counts = {}
    sign_year_counts = {}
    for row in records:
        d = row.get("domain", "")
        if d:
            domain_counts[d] = domain_counts.get(d, 0) + 1
        year = extract_year(row.get("sign_date", ""))
        if year != "未知":
            sign_year_counts[year] = sign_year_counts.get(year, 0) + 1

    stats = {
        "source": "treaty",
        "collection": collection_name,
        "record_count": len(records),
        "domain_distribution": dict(sorted(domain_counts.items(), key=lambda x: -x[1])),
        "sign_year_distribution": dict(sorted(sign_year_counts.items())),
    }
    write_json(collection_root / "stats_report.json", stats)

    md = render_markdown_report(
        f"条约库统计报告 - {collection_name}",
        [
            ("概览", {"collection": collection_name, "record_count": len(records)}),
            ("领域分布", stats["domain_distribution"]),
            ("签署年份分布", stats["sign_year_distribution"]),
        ],
    )
    write_text(collection_root / "stats_report.md", md)
    write_json(
        collection_root / "summary.json",
        {"source": "treaty", "collection": collection_name, "count": len(records)},
    )
    return collection_root


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="外交部条约数据库爬虫")
    parser.add_argument("--search", default="", help="Search keyword")
    parser.add_argument(
        "--collections", nargs="*", default=None, choices=list(COLLECTION_URLS.keys())
    )
    parser.add_argument(
        "--size", type=int, default=None, help="Max items per collection"
    )
    parser.add_argument(
        "--max-pages", type=int, default=None, help="Max pages per collection"
    )
    parser.add_argument("--download", action="store_true", help="Download preview PDFs")
    parser.add_argument(
        "--no-download", action="store_true", help="Metadata only (default)"
    )
    parser.add_argument(
        "--info", default=None, help="Get detail for a specific treaty URL"
    )
    parser.add_argument(
        "--output", "-o", default="./treaty_output", help="Output directory"
    )
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

    output_dir = Path(args.output).expanduser().resolve()
    logger = setup_logger(output_dir, name="treaty_crawler")

    if args.no_cache:
        global _cache
        _cache = _CacheManager(enabled=False, namespace="npc-law-db-treaty")
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
        detail = parse_detail(args.info)
        print(json.dumps(detail, ensure_ascii=False, indent=2))
        return 0

    limiter, forced = init_limiter(args.rate_limit)
    collections = args.collections or DEFAULT_COLLECTIONS
    limiter.init_for_task(
        estimated_requests=(args.size or 100) * len(collections), forced_mode=forced
    )

    download_files = args.download and not args.no_download
    logger.info(
        "Start: collections=%s, keyword=%s, download=%s",
        collections,
        args.search,
        download_files,
    )

    results = []
    for collection in collections:
        logger.info("Collection: %s", collection)
        records = search_collection(
            collection,
            keyword=args.search,
            max_items=args.size,
            max_pages=args.max_pages,
            timeout=args.timeout,
        )
        collection_root = save_results(records, output_dir, collection, download_files)
        results.append(
            {
                "collection": collection,
                "count": len(records),
                "path": str(collection_root),
            }
        )
        logger.info("Done: %d records", len(records))

    summary = {
        "source": "treaty",
        "collections": results,
        "total": sum(r["count"] for r in results),
    }
    write_json(output_dir / "summary.json", summary)
    limiter.print_summary()
    logger.info("All done: %s", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
