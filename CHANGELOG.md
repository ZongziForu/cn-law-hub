# 更新日志

## v2.0 — 数据源大幅扩展与工程质量升级 (2026-07-20)

### 新增七个官方数据源

数据源从 3 个扩展至 **10 个**，覆盖中国法律、法规、规章、政策、党内法规、司法解释、条约等主要官方来源：

| # | 数据源 | 脚本 | 来源 | 类型 |
|---|--------|------|------|------|
| 1 | **国家法律法规数据库 (NPC)** | `scripts/download.py` | `flk.npc.gov.cn` | JSON API |
| 2 | **国家规章库 (Gov Rules)** | `scripts/gov_rules_crawler.py` | `gov.cn/zhengce/xxgk/gjgzk` | Athena API + HTML |
| 3 | **外交条约库 (Treaty)** | `scripts/treaty_crawler.py` | `treaty.mfa.gov.cn` | HTML |
| 4 | **国务院政策文件库** ✨ | `scripts/gov_policy_library.py` | `sousuo.www.gov.cn` | REST API (GET) |
| 5 | **司法部行政法规库** ✨ | `scripts/moj_law_crawler.py` | `xzfg.moj.gov.cn` | HTML |
| 6 | **党内法规库** ✨ | `scripts/party_law_crawler.py` | `www.12371.cn` | HTML |
| 7 | **国防部法规文库** ✨ | `scripts/mod_law_crawler.py` | `www.mod.gov.cn` | HTTP |
| 8 | **税务法规库** ✨ | `scripts/tax_law_crawler.py` | `fgk.chinatax.gov.cn` | REST API (POST) |
| 9 | **生态环境部法规规章** ✨ | `scripts/mee_law_crawler.py` | `www.mee.gov.cn` | HTML |
| 10 | **最高人民法院发布栏目** ✨ | `scripts/court_law_crawler.py` | `www.court.gov.cn` | HTML |

> ✨ = 本次新增

---

### 各数据源用法

#### 国务院政策文件库

覆盖国务院文件、国务院部门文件和政策解读。

```bash
# 标题搜索
python scripts/gov_policy_library.py --search "营商环境" --size 20

# 正文搜索
python scripts/gov_policy_library.py --search "放管服" --range content --size 50

# 按分类筛选：全部 / 国务院文件 / 国务院部门文件 / 解读
python scripts/gov_policy_library.py --search "国务院" --category 国务院文件 --size 100

# 按年份筛选
python scripts/gov_policy_library.py --search "营商环境" --year 2024 --size 50

# 查看政策详情
python scripts/gov_policy_library.py --info "https://www.gov.cn/gongbao/content/xxx.htm"
```

| 参数 | 说明 |
|------|------|
| `--search` | 搜索关键词 |
| `--range title/content` | 搜索范围（标题/正文） |
| `--category` | 分类筛选 |
| `--year` | 发布年份筛选 |
| `--department` | 发文机关筛选 |
| `--sort score/time` | 排序方式（相关度/时间） |

#### 司法部行政法规库

官方行政法规数据库，支持效力状态筛选。

```bash
# 标题搜索
python scripts/moj_law_crawler.py --search "行政处罚" --size 20

# 正文搜索
python scripts/moj_law_crawler.py --search "行政复议" --range content --size 50

# 按效力状态筛选
python scripts/moj_law_crawler.py --search "行政处罚" --status effective --size 100
```

| 参数 | 说明 |
|------|------|
| `--search` | 搜索关键词 |
| `--range title/content` | 搜索范围 |
| `--status all/effective/invalid` | 效力状态筛选 |

#### 党内法规库

覆盖党章、条例、规定、办法、规则、细则等 11 个分类。

```bash
# 全部分类搜索
python scripts/party_law_crawler.py --search "纪律" --size 20

# 按分类筛选
python scripts/party_law_crawler.py --category 条例 --size 50

# 查看详情
python scripts/party_law_crawler.py --info "https://www.12371.cn/2022/01/23/ARTI1642937162249109.shtml"
```

分类：`全部` `党章` `条例` `规定` `办法` `规则` `细则` `党的组织法规` `党的领导法规` `党的自身建设法规` `党的监督保障法规`

> 注意：该站无搜索 API，关键词筛选为客户端标题匹配。

#### 国防部法规文库

覆盖法律法规、白皮书、文件、司法解释、出版物等 8 个分类。

```bash
# 按分类浏览
python scripts/mod_law_crawler.py --category 法律法规 --size 20

# 关键词搜索
python scripts/mod_law_crawler.py --search "军队" --size 50

# 查看详情
python scripts/mod_law_crawler.py --info "http://www.mod.gov.cn/gfbw/fgwx/flfg/16448581.html"
```

分类：`全部` `法律法规` `白皮书` `文件` `司法解释` `出版物` `热点聚焦` `政策解读`

#### 税务法规库

覆盖国家税务总局的法律、行政法规、部门规章、财税文件等 9 个分类，通过 POST API 获取数据。

```bash
# 全部分类搜索
python scripts/tax_law_crawler.py --search "增值税" --size 20

# 按分类筛选
python scripts/tax_law_crawler.py --category 财税文件 --size 50

# 查看详情
python scripts/tax_law_crawler.py --info "https://fgk.chinatax.gov.cn/zcfgk/c102416/c5250687/content.html"
```

分类：`全部` `法律` `行政法规` `国务院文件` `税务部门规章` `财税文件` `税务规范性文件` `其他文件` `工作通知`

> 注意：需要 session cookie（脚本自动管理）。

#### 生态环境部法规规章

覆盖法律、行政法规、规章、生态环境损害赔偿制度、行政复议与执法解释。

```bash
# 全部分类搜索
python scripts/mee_law_crawler.py --search "碳" --size 20

# 按分类筛选
python scripts/mee_law_crawler.py --category 法律 --size 50

# 查看详情
python scripts/mee_law_crawler.py --info "https://www.mee.gov.cn/ywgz/fgbz/fl/202603/t20260313_1146496.shtml"
```

分类：`全部` `法律` `行政法规` `规章` `生态环境损害赔偿制度` `行政复议与执法解释`

> 注意：标准（环保标准）不在此数据源中。

#### 最高人民法院发布栏目

覆盖司法解释、司法文件、重大案件、通知、司法数据等 10 个栏目，支持分页。

```bash
# 全部分类搜索（默认 司法解释 + 司法文件）
python scripts/court_law_crawler.py --search "建设工程" --size 20

# 按分类筛选
python scripts/court_law_crawler.py --category 司法解释 --size 50
python scripts/court_law_crawler.py --category 司法文件 --size 30

# 查看详情
python scripts/court_law_crawler.py --info "https://www.court.gov.cn/fabu/xiangqing/504221.html"
```

分类：`全部` `司法解释` `司法文件` `重大案件` `通知` `司法数据` `大数据专题` `标准化工作` `任免招录` `开庭公告`

---

### 共享模块重构

`scripts/common.py` 拆分为模块化包 `scripts/common/`：

```
scripts/common/
├── __init__.py        # 统一导入 + 向后兼容别名
├── cache.py           # 缓存管理
├── chinese_numerals.py # 中文数字转换
├── cli_utils.py       # CLI 参数辅助
├── constants.py       # 全局常量
├── docx_utils.py      # DOCX 解析与法条提取
├── file_io.py         # 文件读写
├── logger.py          # 日志
├── ratelimit.py       # HTTP 客户端与智能限速
└── text_utils.py      # 文本清洗与工具函数
```

向后兼容：旧脚本中的 `from common import _CacheManager` 等私有名称继续有效。

---

### 安全与稳定性改进

- **TLS 默认开启**：`VERIFY_SSL` 默认值改为 `True`（审计确认全部 11 个 `.gov.cn` 主机 TLS 握手通过）。兼容 `CN_LAW_VERIFY_SSL` 和 `NPC_LAW_VERIFY_SSL` 环境变量。
- **移除全局 SSL 警告抑制**：不再全局调用 `urllib3.disable_warnings()`。
- **修复 4xx 处理**：`http_request()` 现在对 401/403/404 和其他 4xx 明确抛出错误，不重试，不伪装为空结果。
- **Session 支持**：`http_request()` 新增可选 `session` 参数，传入 `requests.Session` 时保留 cookie，支持需要会话的 API（如税务法规库）。
- **Per-attempt 限速**：`limiter.acquire()` 移至每次 HTTP 重试前调用，而非仅在首次前调用。
- **修复 `sys` 导入缺失**：`ratelimit.py` 的 `report_429()` 和 `print_summary()` 中使用 `sys.stderr` 但缺少 `import sys` 已修复。
- **税务法规库完整限速接入**：使用 `http_request(session=session)` 替代私有 `_get_limiter`，享受完整的自适应反馈、429 退避和重试。

---

### SKILL.md 瘦身

- 577 行 → 148 行（减少 74%）
- 移除了内联 API payload、逐源 CLI 示例、冗余参数表至 `references/`
- 新增 `references/setup.md`（环境配置）
- 新增**效力状态强制规则**：仅当官方页面明确标注时才写"现行有效"等，不得推断
- 新增**文件类型归属格式**：区分法律/行政法规/规章/司法解释/党内法规/政策文件等
- 保持宽触发 frontmatter，覆盖全部十个数据源

---

### 测试

新增 **250 个离线测试**，覆盖全部 7 个新数据源：

| 测试文件 | 数量 |
|----------|------|
| `test_gov_policy_library.py` | 26 |
| `test_moj_law_crawler.py` | 20 |
| `test_party_law_crawler.py` | 20 |
| `test_mod_law_crawler.py` | 20 |
| `test_tax_law_crawler.py` | 24 |
| `test_mee_law_crawler.py` | 19 |
| `test_court_law_crawler.py` | 23 |
| `test_new_sources_contract.py` | 56（参数化） |
| `test_common.py` | 23 |
| `test_live_sources.py` | 7（默认跳过） |

运行：`pytest -q -m "not live"` → 250 passed。

在线冒烟测试（需 `CN_LAW_RUN_LIVE=1`）：7 个源全部通过。

---

### 致谢

- **[kasc0206](https://github.com/kasc0206)** — 在 [PR #1](https://github.com/ZongziForu/cn-law-hub/pull/1) 中贡献了国务院政策文件库、司法部行政法规库、党内法规库、国防部法规文库、税务法规库、生态环境部法规规章和最高人民法院发布栏目共 7 个爬虫脚本，将数据源从 3 个大幅扩展至 10 个，并重构了 `scripts/common/` 共享模块，补齐了测试与开发依赖。
- **[Li2zon3](https://github.com/Li2zon3)** — 其 [`law-crawler-unified`](https://github.com/Li2zon3/law-crawler-unified) 项目为国家规章库和外交条约库的实现提供了重要参考。
