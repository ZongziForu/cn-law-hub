# MCP Access (可选接入方式)

The skill (this repo's `SKILL.md` + `scripts/`) is the **primary** way to use
cn-law-hub. MCP is an **additional** access path: one stdio server process that
exposes the same data sources as callable tools to any MCP-compatible agent
(Claude Code, Cline, Cursor, Kimi, Codex, ...). Nothing in the skill path is
changed — `scripts/mcp_server.py` only **reuses** the existing crawler functions.

## Prerequisites

```bash
# Only needed for MCP access (skill / CLI do not require it)
pip install "mcp>=2.0.0"
```

Note: `mcp>=2.0.0` uses the `MCPServer` API. mcp 1.x's `FastMCP` was removed
in 2.0 — do not install `mcp<2.0.0` for this server.

## Server

```bash
python3 scripts/mcp_server.py    # stdio transport; waits for an MCP client
```

It registers 5 tools:

| Tool | 说明 |
|---|---|
| `search_laws(source, keyword, category, size)` | 统一搜索 10 个数据源（npc / gov_policy / moj / party / mod / tax / mee / court / gov_rules / treaty） |
| `get_law_detail(source, url)` | 拉取单条记录的详情（npc 传 bbbs id，其余传详情 URL） |
| `query_article(bbbs_id, query?, grep?)` | 按条文号（如"第三十八条"）或关键词检索某部法律的法条 |
| `preview_law(bbbs_id)` | 预览一部法律的结构：标题、条数、编号格式、前 20 条 |
| `article_search(keyword, law_keyword?, max_laws?, context?)` | 跨多部法律检索法条关键词 |

`search_laws` 的 `category` 对 `gov_rules`（部门规章 / 地方政府规章）和
`treaty`（全部 / 双边 / 多边）为必填；其余源可选。

## Claude Code

Repo root already ships `.mcp.json`, auto-discovered when the project opens:

```json
{
  "mcpServers": {
    "cn-law-hub": {
      "command": "python3",
      "args": ["scripts/mcp_server.py"]
    }
  }
}
```

Verify with `/mcp` — you should see the `cn-law-hub` server and its 5 tools.

## Other agents

| Agent | How to register |
|---|---|
| **Cline / Roo Code** | VS Code settings → MCP servers → add "cn-law-hub" with the same `command`/`args` |
| **Cursor** | Settings → Features → MCP → Add stdio server: `python3 scripts/mcp_server.py` |
| **Kimi / Codex** | Use their MCP config file / CLI `mcp add`, pointing at `python3 <repo>/scripts/mcp_server.py` |

Any agent that speaks the standard MCP stdio protocol works — the server needs
no per-agent code.

## Notes

- All tools return JSON; errors come back as `{"error": ...}` rather than a crash.
- `search_laws` requires network access to the official sources (same as the CLI).
- If `mcp` is not installed, the agent will show a warning for this server;
  the skill path is unaffected.
