---
name: cn-law-hub
description: >-
  用于查询、检索、核验、下载、导出、批量采集中国官方法律法规、规章、条约和具体法条。Use this skill aggressively when the user asks to 查法律、查法规、查条例、查规章、查条约、查法条、查第几条、找法律依据、引用法律依据、核验现行有效、判断是否废止/已修改/尚未生效、下载法规全文、导出法规目录、批量下载法规文件、按关键词检索具体法条、展开法条分析，或在中国法律咨询、案例分析、合规审查、合同审查、劳动争议、行政法分析、公司合规、数据合规、政策研究中需要调用、核验或引用中国现行有效法律法规原文作为依据。Trigger also when phrases such as 依法、依规、依照法律规定、法律法规 imply a need to verify specific statutory authority or article-level text. Covers 国家法律法规数据库 (flk.npc.gov.cn), 国家规章库 (gov.cn), 外交条约库 (treaty.mfa.gov.cn), 国务院政策文件库 (sousuo.www.gov.cn), 司法部行政法规库 (xzfg.moj.gov.cn), 党内法规库 (12371.cn), 国防部法规文库 (mod.gov.cn), 税务法规库 (fgk.chinatax.gov.cn), 生态环境部法规规章 (mee.gov.cn), and 最高人民法院发布栏目 (court.gov.cn). Supports 标题/正文检索, 精确/模糊检索, 时效性过滤, 分类过滤, 分页, 排序, 单篇下载, 批量下载, 法条级抽取, 地区/制定机关分类, and browser fallback. Trigger when the answer may depend on current effective Chinese statutes, regulations, rules, treaties, article text, official document status, or official source attribution. Do not use for purely general legal theory, generic writing, or legal reasoning that does not require retrieving or verifying official Chinese legal documents.
---

# Data Sources

| # | Database | Script | Source | Type |
|---|---|---|---|---|
| 1 | **国家法律法规数据库 (NPC)** | `scripts/download.py` | `flk.npc.gov.cn` | JSON API |
| 2 | **国家规章库 (Gov Rules)** | `scripts/gov_rules_crawler.py` | `gov.cn/zhengce/xxgk/gjgzk` | Athena API + HTML |
| 3 | **外交条约库 (Treaty)** | `scripts/treaty_crawler.py` | `treaty.mfa.gov.cn` | HTML |
| 4 | **国务院政策文件库** | `scripts/gov_policy_library.py` | `sousuo.www.gov.cn` | REST API (GET) |
| 5 | **司法部行政法规库** | `scripts/moj_law_crawler.py` | `xzfg.moj.gov.cn` | HTML |
| 6 | **党内法规库** | `scripts/party_law_crawler.py` | `www.12371.cn` | HTML |
| 7 | **国防部法规文库** | `scripts/mod_law_crawler.py` | `www.mod.gov.cn` | HTTP |
| 8 | **税务法规库** | `scripts/tax_law_crawler.py` | `fgk.chinatax.gov.cn` | REST API (POST) |
| 9 | **生态环境部法规规章** | `scripts/mee_law_crawler.py` | `mee.gov.cn` | HTML |
| 10 | **最高人民法院发布栏目** | `scripts/court_law_crawler.py` | `court.gov.cn` | HTML |

All scripts share `--search`, `--info`, `--size`, `--output`, `--rate-limit`, `--no-cache`, `--cache-stats`, `--cache-clear`. Run `python <script> --help` for full parameter lists.

---

# Core Rules

## Search Strategy (applies to ALL data sources)

**Decide before calling the script — never default to fuzzy for everything:**

- **Known title** (e.g. "物业管理条例", "北京市生活垃圾管理条例"): use `--exact` to reduce noise.
- **Broad topic** (e.g. "出租车", "环境保护"): use fuzzy search (default).
- **Full-text match**: add `--range content` when you need documents where the keyword appears in the body, not just the title.
- **Ambiguous**: ask the user, or run both exact+fuzzy and compare.

## Status Filtering

NPC status codes (`sxx` / `--status`):

| Code | Meaning |
|------|---------|
| `1` | **已废止** |
| `2` | **已修改** |
| `3` | **现行有效** |
| `4` | **尚未生效** |

Other sources use their own status values (e.g. `--status effective` for MoJ). Check `--help` per script.

## Article-Level Queries (NPC)

For individual articles instead of full documents:

| Command | When | Output |
|---|---|---|
| `--preview <id>` | Understand structure first | Title, article count, TOC |
| `--article <id> "第X条"` | Know the article number | Single article text |
| `--article <id> --grep "kw"` | Find articles by keyword in one law | All matching articles |

Supports Chinese numerals (`第三十八条`), Arabic (`第38条`), or bare numbers (`38`).

For cross-law article search, use `scripts/article_search.py <keyword> --max-laws N`.

## Rate Limiting

Auto mode picks by estimated requests: **OFF** (≤10), **FIXED** 5 req/s (11–100), **ADAPTIVE** 1–8 req/s with 429 backoff (>100). Override: `--rate-limit {off|fixed|adaptive}`.

## Caching

Local file cache enabled (~/.cache/ per namespace). Search results: 1h TTL. Detail metadata: 24h. DOCX: 7 days. Use `--no-cache` to bypass, `--cache-stats` to inspect.

---

# Validity Rules — MANDATORY

1. Only state **现行有效**, **已废止**, **已修改**, or **尚未生效** when the official page or API response **explicitly** provides that status.
2. If the source has **no explicit validity field**, say: **"官方页面未明确标注效力状态"**.
3. **Do not infer** validity from file accessibility or recency of publication date.
4. Always return: official URL, file type, issuing authority, publication date, and retrieval date — even when status is absent.
5. For same-name / multi-version documents, flag the ambiguity and verify amendment, repeal, and effective-date information.
6. Distinguish document types: 法律, 行政法规, 地方性法规, 规章, 司法解释, 司法文件, 党内法规, 政策文件, 通知, 案例, 条约. Do not conflate.
7. Never write "现行法律" as a generic label for all official publications.

---

# Document Type Attribution

When reporting results, always identify the document type and source database explicitly. Use the format:

> **来源**: [数据库名称] ([URL])  
> **文件类型**: [法律/行政法规/规章/司法解释/党内法规/政策文件/通知/...]  
> **发布机关**: [authority]  
> **发布日期**: [date]  
> **效力状态**: [现行有效/已废止/...] 或 "官方页面未明确标注效力状态"

---

# Script Routing Summary

| Script | Purpose | Key flags | Output dir |
|---|---|---|---|
| `scripts/download.py` | NPC search, download, article, preview | `--search`, `--exact`, `--range`, `--status`, `--download`, `--article`, `--preview`, `--urls-only` | stdout, files |
| `scripts/article_search.py` | Cross-law article-level search | `keyword`, `--law`, `--range`, `--max-laws`, `--context`, `--json`, `--offset`, `--resume` | stdout |
| `scripts/gov_rules_crawler.py` | Gov.cn rules | `--search`, `--categories`, `--download`, `--info` | `gov_rules_output/` |
| `scripts/treaty_crawler.py` | MFA treaties | `--search`, `--collections`, `--download`, `--info` | `treaty_output/` |
| `scripts/gov_policy_library.py` | State Council policies | `--search`, `--range`, `--category`, `--year` | `gov_policy_output/` |
| `scripts/moj_law_crawler.py` | MoJ admin regulations | `--search`, `--range`, `--status` | `moj_law_output/` |
| `scripts/party_law_crawler.py` | Party regulations (12371.cn) | `--search`, `--category` | `party_law_output/` |
| `scripts/mod_law_crawler.py` | MOD law library | `--search`, `--category` | `mod_law_output/` |
| `scripts/tax_law_crawler.py` | Tax regulations (chinatax) | `--search`, `--category` | `tax_law_output/` |
| `scripts/mee_law_crawler.py` | MEE env regulations | `--search`, `--category` | `mee_law_output/` |
| `scripts/court_law_crawler.py` | SPC announcements | `--search`, `--category` | `court_law_output/` |
| `scripts/region_classifier.py` | Province/city classification | `--classify`, `--matrix` | JSON/CSV |

Each script has `--help`. Run it for detailed parameter lists.

---

# Reference Files

Read these on demand, not proactively:

| File | Read when... |
|---|---|
| `references/setup.md` | First run, dependency issues, or switching agent environments |
| `references/api_reference.md` | Need full NPC API payloads, field mappings, auth, or pagination details |
| `references/gov_rules_api_reference.md` | Gov Rules auth issues (401/403) or response field parsing |
| `references/gov_policy_api_reference.md` | Need State Council API parameter details beyond `--help` |
| `references/treaty_api_reference.md` | Treaty HTML structure or field extraction patterns |
| `references/page_structure.md` | Browser automation — page layout, selectors, UI-only search flow |
| `references/kimi_bridge_adapter.md` | Running on Kimi Agent or Claude Code + kimi-webbridge |
| `references/codex_adapter.md` | Running on Codex |
| `references/batch_collection.md` | Large-scale collection (200+ items), batch download workflows |

Browser fallback: only when the API/script fails or UI-only search is required. Read `references/page_structure.md` first.

---

# Key Notes by Data Source

- **NPC**: `ossFile` paths from detail API are not directly downloadable — always use `--download`. `bbbs` = unique law ID.
- **Gov Rules**: Requires dynamic RSA auth from the frontend JS bundle; may expire during long runs. Restart on 401/403.
- **Treaty**: Pure HTML, no API. Collections: `全部`, `双边`, `多边`.
- **Party Law (12371.cn)**: No search API; keyword filtering is client-side on titles only.
- **MOD**: Static HTML, no search API. Client-side title filtering.
- **Tax**: POST API, requires session cookie (auto-managed). Channel ID auto-discovered.
- **MEE**: Static HTML, categories pre-loaded in page. No search API. Standards (环保标准) excluded.
- **Court**: List pages paginated (`/fabu/gengduo/{id}.html` → `{id}_{n}.html`). No search API.
