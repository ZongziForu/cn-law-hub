# Setup and Environment

## Python Setup

```bash
pip install -r requirements.txt
# Optional — for old .doc format (pre-2007 Word):
brew install antiword catdoc     # macOS
apt-get install antiword catdoc  # Linux
```

## Agent Environment Selection

This skill supports multiple agent environments. Read the adapter for your env first:

| Environment | Read | Tool prerequisite |
|---|---|---|
| **Kimi Agent (cloud)** | `kimi_bridge_adapter.md` | Native `mshtools-browser_*` |
| **Claude Code (local via kimi-webbridge)** | `kimi_bridge_adapter.md` | Invoke `kimi-webbridge` first |
| **Codex** | `codex_adapter.md` | `mcp__node_repl__js` for browser |

Kimi Agent and Claude Code via kimi-webbridge share the same adapter (same browser-operation semantics).

## Browser Automation

When the API/script fails, or UI-only advanced search is required, read `page_structure.md` for page layout and browser automation details before operating the browser directly.
