# CN Law Hub — 中国法条检索 / PRC Statute & Regulation Search for AI Agents

[![GitHub](https://img.shields.io/badge/GitHub-ZongziForu%2Fcn--law--hub-blue)](https://github.com/ZongziForu/cn-law-hub) [![小红书](https://img.shields.io/badge/小红书-RedSkill%20市场-red)](http://xhslink.cn/o/3HYck1C99xr)

面向 Claude Code、Codex、Kimi 等 AI Agent 的中国大陆法条与法律法规检索 Skill，直接检索全国人大、国务院、司法部、最高人民法院等 10 个官方来源，支持具体条文检索、跨法规正文搜索、现行有效筛选与官方原文下载。

Chinese legal research Agent Skill for retrieving and verifying Chinese laws from official sources.

**覆盖 10 个官方数据源：**

1. **国家法律法规数据库（NPC）** — `flk.npc.gov.cn`
2. **国家规章库（Gov Rules）** — `gov.cn/zhengce/xxgk/gjgzk/`
3. **外交条约库（Treaty）** — `treaty.mfa.gov.cn`
4. **国务院政策文件库** — `sousuo.www.gov.cn`
5. **司法部行政法规库** — `xzfg.moj.gov.cn`
6. **党内法规库** — `www.12371.cn/special/dnfg/`
7. **国防部法规文库** — `www.mod.gov.cn/gfbw/fgwx/`
8. **税务法规库** — `fgk.chinatax.gov.cn`
9. **生态环境部法规规章** — `mee.gov.cn/ywgz/fgbz/`
10. **最高人民法院发布栏目** — `court.gov.cn/fabu/`

| Official sources | Article-level search | Cross-law search |
|---|---|---|
| Validity filtering | Chinese local & national regulations | Claude Code & Codex |

---

## 什么时候使用这个 Skill

当你需要查询、核验、下载或引用中国官方法律法规、规章、条约和具体法条时，可以直接让 agent 使用本 skill。多数情况下，你不需要手动运行脚本，只需要用自然语言说明任务，agent 会根据 `SKILL.md` 自动选择合适的数据源、脚本和参数。

如果你希望确保在当前工作中使用本 skill，也可以在请求中直接使用 `/cn-law-hub` 指令（尤其在你没有使用能力较强的模型时）。

典型场景包括：查法规全文、核验现行有效状态、查询某法第几条、按关键词检索具体法条、为法律咨询/案例分析/合规审查提供官方法条依据、批量下载法规文件或导出法规目录。

例如：

```text
帮我查《劳动合同法》第三十八条，并引用现行有效版本。
找一下关于物业管理的现行有效地方性法规。
帮我检索包含“违约金”的具体法条，并按法规名称列出来。
这个劳动争议案例可能涉及哪些现行有效法律依据？
```

<details>
<summary>更多可触发本 skill 的中文表达</summary>

你可以使用类似表达：

- 查法律、查法规、查条例、查规章、查条约、查法条
- 查第几条、查询某法第几条、找某条法律依据
- 找法律依据、引用法律依据、引用法条、展开法条分析
- 核验现行有效、判断是否废止、是否已修改、是否尚未生效
- 下载法规全文、批量下载法规文件、导出法规目录
- 按关键词检索具体法条、跨法规查找相关条文
- 查询地方性法规、按地区/制定机关分类
- 在法律咨询、案例分析、合规审查、合同审查、劳动争议、行政法分析、公司合规、数据合规、政策研究中，需要调用中国现行有效法律法规原文作为依据
- 当问题中出现“依法”“依规”“依照法律规定”“根据现行规定”等表达，并且需要核验具体法律依据时，也适合调用本 skill

如果只是一般法律概念解释、普通写作润色，且不需要核验官方法律法规原文，则不一定需要调用本 skill。

</details>

---

## 功能概览

- **多数据源支持**：NPC 国家法律法规数据库、国家规章库、外交条约库、国务院政策文件库、司法部行政法规库、党内法规库、国防部法规文库、税务法规库、生态环境部法规规章、最高人民法院发布栏目
- **标题/正文检索**：支持标题关键词、正文关键词两种搜索范围
- **精确/模糊策略**：已知标题用 `--exact` 精确匹配，主题/关键词用模糊匹配
- **现行有效状态筛选**：`--status 3` 仅返回现行有效法规
- **单篇下载**：DOCX（WPS 版）/ PDF（公报原版）
- **单条法条查询**：`--preview` 查看结构，`--article` 按条号或关键词查条文
- **跨法规法条级搜索**：`scripts/article_search.py` 在多部法规正文中定位具体法条
- **批量采集**：支持一次性采集 200–300 条法规的完整工作流
- **智能限速**：根据任务大小自动选择 OFF / FIXED / ADAPTIVE 模式，避免 429
- **本地缓存**：搜索结果、元数据、DOCX 文件默认缓存，复访提速
- **URL 导出**：云端 agent 可只导出签名下载 URL，供本地下载使用
- **地域/制定机关分类**：内置省市映射，自动识别国家级、省级、设区市级
- **多环境支持**：Kimi Agent、Claude Code via kimi-webbridge、Codex；其中 Kimi Agent 与 Claude Code via kimi-webbridge 共用同一套 browser adapter，因为两者的浏览器操作语义一致

---

## 安装

建议使用 Python 3.10+。

```bash
pip install -r requirements.txt
```

部分旧法规可能使用 `.doc` 格式，需要安装可选系统工具：

```bash
# macOS
brew install antiword catdoc

# Debian/Ubuntu
apt-get install antiword catdoc
```

如需通过 **MCP** 接入（可选，见下文）：

```bash
pip install "mcp>=2.0.0"
```

---

### 一键安装

两种接入方式**二选一**，代码相同，只是接入形态不同：

| | **Skill 版**（推荐，主路径） | **MCP 版**（可选） |
|---|---|---|
| 形态 | 注册为 agent 的 Skill，自然语言或 `/cn-law-hub` 调用 | 一个 stdio server，暴露 5 个 MCP 工具 |
| 适用 | Claude Code / Codex / Kimi 等支持 skill 的 agent | 任意 MCP 兼容 agent（Claude Code / Cline / Cursor / Kimi / Codex） |
| 依赖 | 仅 `requirements.txt` | 额外 `pip install "mcp>=2.0.0"` |
| 配置 | agent 注册 skill | 见 `references/mcp_setup.md`；Claude Code 自动读 `.mcp.json` |

发布版请从 [Releases](https://github.com/ZongziForu/cn-law-hub/releases) 下载 `Source code` 压缩包。

#### 方式 A：Skill 版（用 Agent 自动配置）

直接把仓库链接丢给 agent，让它自己完成下载、安装依赖和注册 skill。复制以下提示词即可：

> 请安装并配置这个 Skill：https://github.com/ZongziForu/cn-law-hub/releases/tag/v2.0.1
>
> 从上述 release 下载 Source code 压缩包，或 clone 仓库。先阅读仓库中的 SKILL.md 和 references/setup.md，并识别当前平台正确的 skills 目录。不要直接把整个仓库复制到最终安装目录；请先下载到临时目录，再仅安装以下运行时文件：
> - `SKILL.md`
> - `scripts/`
> - `references/`
> - `requirements.txt`
> - `LICENSE`
> - `LICENSE-APACHE`
> - `NOTICE`
>
> 不要拷贝 `tests/`、`pytest.ini`、`CHANGELOG.md`、`requirements-dev.txt`、`.mcp.json`、`*.pyc`、`__pycache__`。
>
> 安装依赖：`pip install -r requirements.txt`（Python 3.10+）。注册完成后，用"帮我查《劳动合同法》第三十八条"验证。

#### 方式 B：MCP 版

```bash
pip install "mcp>=2.0.0"
python3 scripts/mcp_server.py        # 启动 stdio server（等待 MCP 客户端连接）
```

Claude Code 打开仓库即自动读取根目录 [`.mcp.json`](.mcp.json) 接入；其他 agent 的配置方法见 [`references/mcp_setup.md`](references/mcp_setup.md)。

---

## 快速开始

多数情况下，你不需要手动执行下面的命令。只要用自然语言向 agent 描述任务，agent 会根据 `SKILL.md` 自动选择合适的数据源、脚本和参数。

下面的命令主要用于本地手动运行、调试、复现结果，或帮助你理解本 skill 的核心能力。

### 国家法律法规数据库（NPC）

```bash
# 精确搜索已知法规名，并优先返回现行有效版本
python scripts/download.py --search "物业管理条例" --exact --status 3 --size 20

# 按主题/关键词模糊搜索
python scripts/download.py --search "出租车" --status 3 --size 50

# 下载单部法规
python scripts/download.py --download <bbbs_id> --format docx output.doc

# 查看法规结构并查询具体法条
python scripts/download.py --preview <bbbs_id>
python scripts/download.py --article <bbbs_id> "第三十八条"

# 跨法规检索具体法条
python scripts/article_search.py "违约金" --range content --max-laws 5 --context 1
```

### 国家规章库与外交条约库

```bash
# 国家规章库
python scripts/gov_rules_crawler.py --search "管理办法" --categories 部门规章 --size 20

# 外交条约库
python scripts/treaty_crawler.py --collections 双边 --search "上海合作组织" --size 20
```

更多参数见 [`SKILL.md`](SKILL.md) 和 [`references/`](references/)。

---

## 常见工作流

### 查询单条/多条法条

当你只需要核对某一条或搜索某部法规内的关键词时，不必把整部法规塞进 agent 上下文。

```bash
# 预览法规结构
python scripts/download.py --preview <bbbs_id>

# 按条号查询（自动识别中文/阿拉伯数字）
python scripts/download.py --article <bbbs_id> "第三十八条"
python scripts/download.py --article <bbbs_id> "第38条"
python scripts/download.py --article <bbbs_id> "38"

# 在单部法规中 grep 关键词
python scripts/download.py --article <bbbs_id> --grep "经济补偿"
```

### 跨法规法条级搜索

`scripts/article_search.py` 用于在多部法规中查找包含关键词的具体法条：

```bash
# 在标题含关键词的法规中搜索
python scripts/article_search.py "违约金" --max-laws 5 --context 1

# 在全文含关键词的法规中搜索
python scripts/article_search.py "违约金" --range content --max-laws 5

# 限定只查某一部法规
python scripts/article_search.py "善意取得" --law 民法典 --context 0

# JSON 输出
python scripts/article_search.py "违约金" --max-laws 3 --json

# 分批检索
python scripts/article_search.py "违约金" --range content --max-laws 5 --offset 5
python scripts/article_search.py "违约金" --range content --max-laws 5 --resume
```

### 智能限速与缓存

```bash
# 大任务使用自适应限速
python scripts/download.py --search "出租车" --urls-only --size 200 --rate-limit adaptive

# 查看缓存
python scripts/download.py --cache-stats

# 单次禁用缓存
python scripts/download.py --no-cache --info <bbbs_id>

# 清空缓存
python scripts/download.py --cache-clear
```

缓存位置：`~/.cache/{namespace}/`（共 10 个 namespace，每个数据源独立）。

**缓存 TTL 与自动清理：**
- 搜索结果/列表页缓存：30 分钟 ~ 1 小时
- 详情/元数据缓存：24 小时
- DOCX 下载缓存：7 天
- 过期缓存由 `CacheManager` 在每次运行时机会式自动清理（每 7 天最多完整扫描一次），无需手动干预
- `--cache-clear` 用于立即清空当前数据源的全部缓存

### 地域分类

城市级 authority 通常不含省份名，例如 "广州市人民代表大会常务委员会" 不会包含 "广东省"。`region_classifier.py` 自动处理这个问题：

```bash
python scripts/download.py --search "物业管理条例" --urls-only --size 100 > urls.json
python scripts/region_classifier.py --classify < urls.json > classified.json
python scripts/region_classifier.py --matrix matrix.csv < classified.json
```

<details>
<summary>Python API 示例</summary>

```python
from scripts.region_classifier import classify_by_authority

classify_by_authority("广州市人民代表大会常务委员会")
# {
#   "province": "广东省",
#   "province_short": "广东",
#   "city": "广州市",
#   "level": "city",
#   "is_municipality": False,
#   "authority": "广州市人民代表大会常务委员会"
# }
```

</details>

### 批量采集

详见 [`references/batch_collection.md`](references/batch_collection.md)。批量采集请使用自适应限速，并避免重复、大量、高频请求。

---

## MCP 接入（可选）

**MCP 版是什么**：把同一套检索能力封装成一个标准 MCP server（一个进程、
5 个工具），任何 MCP 兼容 agent 都能连接调用。它与 Skill 版共享全部
`scripts/` 爬虫代码，`mcp_server.py` 只做转发，不修改任何现有文件。

**和 Skill 版怎么选**：
- 用 **Skill 版**：想让 agent 根据自然语言自动选数据源、直接 `/cn-law-hub` 调用，或需要下载原文、批量采集等完整工作流 —— 这是主路径。
- 用 **MCP 版**：更习惯"一个 server、N 个工具"的显式调用，或你的 agent 支持 MCP 但不支持自定义 skill（如 Cursor、Cline）。

```bash
pip install "mcp>=2.0.0"
python3 scripts/mcp_server.py        # 启动 stdio server（等待 MCP 客户端连接）
```

```bash
pip install "mcp>=2.0.0"
python3 scripts/mcp_server.py        # 启动 stdio server（等待 MCP 客户端连接）
```

Claude Code 会自动读取仓库根目录的 [`.mcp.json`](.mcp.json)，打开项目即接入；
其他 agent 的配置见 [`references/mcp_setup.md`](references/mcp_setup.md)。

提供 5 个工具：

| 工具 | 说明 |
|---|---|
| `search_laws(source, keyword, category?, size?)` | 统一搜索 10 个数据源 |
| `get_law_detail(source, url)` | 拉取单条记录详情 |
| `query_article(bbbs_id, query?, grep?)` | 按条号/关键词查单部法律法条 |
| `preview_law(bbbs_id)` | 预览法律结构（条数 / 编号格式 / 前 20 条） |
| `article_search(keyword, law_keyword?, max_laws?, context?)` | 跨法规法条级搜索 |

---

## 文件结构

```
cn-law-hub/
├── SKILL.md                      # 给 agent 看的 skill 主文档
├── README.md                     # 本文件
├── CHANGELOG.md                  # 更新日志
├── LICENSE                       # 临时竞赛许可证 v1.1（2026-09-21 前生效）
├── LICENSE-APACHE                # Apache-2.0 标准文本（2026-09-21 起生效）
├── NOTICE                        # 版权与贡献者声明（Apache-2.0 要求）
├── CITATION.cff                  # 机器可读引用信息
├── requirements.txt              # Python 依赖
├── requirements-dev.txt          # 开发依赖（测试/覆盖率）
├── pytest.ini                    # pytest 配置
├── .mcp.json                     # Claude Code MCP 配置（可选，MCP 接入用）
├── scripts/
│   ├── common/                   # 共享工具包
│   │   ├── __init__.py           # 统一导入与向后兼容别名
│   │   ├── cache.py              # 缓存管理
│   │   ├── chinese_numerals.py   # 中文数字转换
│   │   ├── cli_utils.py          # CLI 参数辅助
│   │   ├── constants.py          # 全局常量
│   │   ├── docx_utils.py         # DOCX 解析与法条提取
│   │   ├── file_io.py            # 文件读写
│   │   ├── logger.py             # 日志
│   │   ├── ratelimit.py          # HTTP 客户端与智能限速
│   │   └── text_utils.py         # 文本清洗与工具函数
│   ├── download.py               # NPC 搜索、下载、导出 URL、预览/查询法条
│   ├── article_search.py         # NPC 跨法规法条级关键词搜索
│   ├── gov_rules_crawler.py      # 国家规章库爬虫
│   ├── treaty_crawler.py         # 外交条约库爬虫
│   ├── gov_policy_library.py     # 国务院政策文件库
│   ├── moj_law_crawler.py        # 司法部行政法规库
│   ├── party_law_crawler.py      # 党内法规库 (12371.cn)
│   ├── mod_law_crawler.py        # 国防部法规文库
│   ├── tax_law_crawler.py        # 税务法规库 (国家税务总局)
│   ├── mee_law_crawler.py        # 生态环境部法规规章
│   ├── court_law_crawler.py      # 最高人民法院发布栏目
│   ├── mcp_server.py             # MCP server（可选接入，复用各爬虫函数）
│   └── region_classifier.py      # 地域分类与存在性矩阵
├── references/
│   ├── api_reference.md          # NPC API 端点与参数参考
│   ├── gov_rules_api_reference.md # 国家规章库 API 与认证参考
│   ├── gov_policy_api_reference.md # 国务院政策文件库 API 参考
│   ├── treaty_api_reference.md   # 外交条约库 HTML 结构参考
│   ├── setup.md                  # 环境配置与平台适配
│   ├── batch_collection.md       # 批量采集指南
│   ├── page_structure.md         # 页面结构与浏览器操作
│   ├── kimi_bridge_adapter.md    # Claude Code / Kimi Agent 适配
│   ├── codex_adapter.md          # Codex 适配
│   └── mcp_setup.md              # MCP 接入配置（Claude Code / 其他 agent）
└── tests/
    ├── conftest.py               # pytest fixtures
    ├── fixtures/                 # 各数据源 mock 数据
    │   ├── court/
    │   ├── gov_policy/
    │   ├── mee/
    │   ├── mod/
    │   ├── moj/
    │   ├── party/
    │   └── tax/
    ├── test_article_search.py    # 法条搜索测试
    ├── test_common.py            # 共享模块测试
    ├── test_download.py          # NPC 下载测试
    ├── test_gov_policy_library.py # 国务院政策文件库测试
    ├── test_moj_law_crawler.py   # 司法部行政法规库测试
    ├── test_party_law_crawler.py # 党内法规库测试
    ├── test_mod_law_crawler.py   # 国防部法规文库测试
    ├── test_tax_law_crawler.py   # 税务法规库测试
    ├── test_mee_law_crawler.py   # 生态环境部法规测试
    ├── test_court_law_crawler.py # 最高法栏目测试
    ├── test_new_sources_contract.py # 七源契约测试
    ├── test_live_sources.py      # 在线冒烟测试（默认跳过）
    └── test_region_classifier.py # 地域分类测试
```

---

## 致谢

- **数据源贡献者** — 感谢 [kasc0206](https://github.com/kasc0206) 在 [PR #1](https://github.com/ZongziForu/cn-law-hub/pull/1) 中贡献了国务院政策文件库、司法部行政法规库、党内法规库、国防部法规文库、税务法规库、生态环境部法规规章和最高人民法院发布栏目共 7 个爬虫脚本，将数据源从 3 个大幅扩展至 10 个，并重构了 `scripts/common/` 共享模块，补齐了测试与开发依赖，大大提升了本项目的覆盖面与工程质量。
- 特别感谢 [Li2zon3](https://github.com/Li2zon3) 的 [`law-crawler-unified`](https://github.com/Li2zon3/law-crawler-unified) 项目，国家规章库（`scripts/gov_rules_crawler.py`）和外交条约库（`scripts/treaty_crawler.py`）的实现大量参考了其中的思路与方案，帮了很大的忙。

---

## 使用倡议

官方公共法律数据库的维护不易，请大家在使用时保持克制，尽量避免大量高频请求。**本项目在批量采集、搜索和下载等功能中已经内置了不同强度的智能限速（小任务关闭限速、中等任务固定限速、大任务自适应限速）**，希望在不明显影响使用体验的前提下，尽量减少对目标网站造成的负担。请珍惜并合理使用这些公开资源。

---

## 免责声明

本工具仅用于学习、研究、合规核验与个人/机构内部的辅助检索。请遵守 `flk.npc.gov.cn`、`gov.cn`、`treaty.mfa.gov.cn`、`xzfg.moj.gov.cn`、`12371.cn`、`mod.gov.cn`、`fgk.chinatax.gov.cn`、`mee.gov.cn` 和 `court.gov.cn` 等官方数据库的使用规则，避免高频请求、重复批量抓取或对目标网站造成额外负担。

本项目的代码许可请以仓库中的 [LICENSE](LICENSE) 文件为准。这个工具之前一直没有写 license，在此坦诚说明一下：

> 这个工具之前一直没有写license。本人下个月参加法大的第四届大学生数据法治实验模型竞赛，可能要在作品中使用这个工具里的部分代码，为了避免作品的功能冲突，请其他参赛选手不要以本工具作为核心功能之一。9.20提交作品后，本项目自动转为Apache-2.0。

因此在 **2026-09-21 00:00:00（CST）** 之前，本项目为**源码开放**（source-available）的临时竞赛许可证（[LICENSE](LICENSE)）：一般情况下可自由使用、修改、分发，唯一例外是**不得将本工具作为第四届大学生数据法治实验模型竞赛参赛作品的核心功能之一**。到期后自动转为 Apache-2.0（[LICENSE-APACHE](LICENSE-APACHE)），届时不再有任何使用限制。

此外，尽管许可证允许，本项目仍不建议**大量抓取官方法律数据库、镜像官方数据、转售数据、包装成收费数据服务**等可能涉及官方数据再利用合规风险的商业化采集行为。上述行为访问量较大，可能影响目标网站正常运营，且带有盈利性，具有合规风险。使用者应自行评估其使用场景的合法性、合规性和对官方公共资源的影响。

本工具不提供法律意见，也不能替代律师、合规顾问或官方渠道的判断。对于法律文本的时效性、完整性和适用性，请以官方公布内容为准。

---

### 关于作者 / Contact

有任何问题欢迎随时交流！你可以从以下任何一种方式找到我～

| 平台       | 名称                      | 链接 / 联系方式                                               |
| ---------- | ------------------------- | ------------------------------------------------------------- |
| 小红书     | 只有肉粽子才算是粽子ney！ | [点击访问](https://xhslink.com/m/5XGgBInSyJc)                 |
| 微信公众号 | 正在施工的二层楼          | [点击访问](https://mp.weixin.qq.com/s/KUhM7u6ajCfLsw0KDXluZQ) |
| 邮箱       | —                         | `yqc0122@163.com`                                             |

---

## Citation

如果你在论文、报告、课程作业或参赛作品中使用了本工具，欢迎按如下方式引用：

```bibtex
@software{cn_law_hub_2026,
  author = {ZongziForu},
  title = {CN Law Hub: Chinese Legal Research and Retrieval Agent Skill},
  year = {2026},
  url = {https://github.com/ZongziForu/cn-law-hub}
}
```

机器可读的引用信息见仓库中的 [CITATION.cff](CITATION.cff)。

---

<details>
<summary>English Summary</summary>

## What this project does

CN Law Hub is a Claude Code / Kimi Agent / Codex skill for searching, verifying, downloading, and exporting Chinese legal documents from ten official databases:

- National Laws and Regulations Database (`flk.npc.gov.cn`)
- State Council Rules Database (`gov.cn/zhengce/xxgk/gjgzk/`)
- Ministry of Foreign Affairs Treaty Database (`treaty.mfa.gov.cn`)
- State Council Policy Document Library (`sousuo.www.gov.cn`)
- Ministry of Justice Administrative Regulations (`xzfg.moj.gov.cn`)
- Party Regulations Database (`12371.cn/special/dnfg/`)
- Ministry of National Defense Law Library (`mod.gov.cn/gfbw/fgwx/`)
- State Taxation Administration Law Database (`fgk.chinatax.gov.cn`)
- Ministry of Ecology and Environment Regulations (`mee.gov.cn/ywgz/fgbz/`)
- Supreme People's Court Announcements (`court.gov.cn/fabu/`)

## Installation

```bash
pip install -r requirements.txt
```

Optional: some older regulations use `.doc` format:

```bash
# macOS
brew install antiword catdoc

# Debian/Ubuntu
apt-get install antiword catdoc
```

### Optional MCP access

The skill path remains the primary way to use this repo. MCP is an optional
extra: `scripts/mcp_server.py` exposes the same sources as tools to any
MCP-compatible agent. Install with `pip install "mcp>=2.0.0"` and see
`references/mcp_setup.md`.

## Quick Start

In most cases, you do not need to run these commands manually. Describe the task in natural language, and the agent will choose the appropriate database, script, and parameters based on SKILL.md.

The commands below are mainly for local manual use, debugging, reproducing results, or understanding the skill’s core capabilities.

```bash
# NPC: exact title search
python scripts/download.py --search "物业管理条例" --exact --status 3 --size 20

# NPC: article lookup
python scripts/download.py --article <bbbs_id> "第三十八条"

# NPC: article-level search across laws
python scripts/article_search.py "违约金" --range content --max-laws 5 --context 1

# State Council Rules
python scripts/gov_rules_crawler.py --search "管理办法" --categories 部门规章 --size 20

# MFA Treaties
python scripts/treaty_crawler.py --collections 双边 --search "上海合作组织" --size 20
```

The official databases are Chinese-language sources; Chinese keywords and official Chinese titles usually produce the best results.

## Disclaimer

CN Law Hub has long shipped without a license. Its author is joining the 4th Data Rule-of-Law Experimental Model Competition (第四届大学生数据法治实验模型竞赛) at China University of Political Science and Law next month and may reuse part of this project's code in their entry. To avoid feature conflicts between competition entries, other contestants are asked not to use this tool as a core feature of their entries. After the entry is submitted on 9.20, the project automatically transitions to Apache-2.0.

Until 2026-09-21 00:00:00 CST, the project is under the source-available CN Law Hub Temporary Competition License v1.1 ([LICENSE](LICENSE)): general use, modification and redistribution are permitted, except that the tool (or a substantial part of it) may not be used as a core feature of a Competition entry before the Transition Time. From 2026-09-21 CST onward, it is licensed under Apache-2.0 ([LICENSE-APACHE](LICENSE-APACHE)).

Although the license permits commercial use, large-scale extraction, mirroring, resale, or paid repackaging of official legal data is not recommended, as it may raise compliance risks. This tool does not provide legal advice; official publications remain authoritative.

</details>
