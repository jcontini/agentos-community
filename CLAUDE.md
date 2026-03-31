# AgentOS Community — Agent Instructions

> **Read before writing any code.**

## Required reading

Before editing any skill YAML, Python module, or shape file, read the relevant pages from the Skill Book (`docs/`). At minimum:

1. **[Shapes](docs/skills/shapes.md)** — entity schemas, field types, design principles, how operations return shape-native data
2. **[Skill Anatomy](docs/skills/anatomy.md)** — folder structure, entity vs local control patterns
3. **[Operations](docs/skills/operations.md)** — `returns:`, entity ops, action ops, capabilities
4. **[Python Skills](docs/skills/python.md)** — Python executor, `_call` dispatch, shape-native returns

For auth work, also read [Connections & Auth](docs/skills/connections.md) and [Auth Flows](docs/skills/auth-flows.md).
For reverse engineering, start at [Reverse Engineering Overview](docs/reverse-engineering/overview.md).

## Key rules

- **No adapters.** Operations declare `returns: entity[]` pointing to a shape. Python returns dicts matching the shape directly. No mapping layer.
- **Shapes are the contract.** Shape files in `shapes/` define field names, types, relations, and display rules. Python code maps raw API data to shape fields.
- **Every file is a template.** Other agents copy whatever patterns they see. One way to do things, everywhere.
- **HTML parsing: `lxml` with `cssselect`.** No BeautifulSoup, no regex on HTML.
- **All I/O through SDK modules.** `http.get/post`, `shell.run`, `sql.query`. Never `urllib`, `subprocess`, `sqlite3`, `requests`, `httpx`.
- **No Playwright in skills** except the `playwright` skill itself.
- **No runtime fallbacks.** If a selector breaks, fix it. Don't ship fallback chains.
- **No legacy code.** If something is unused, delete it.

## Testing

Test through MCP, not just by reading YAML:

```bash
npm run validate -- <skill>
npm run mcp:call -- --skill <skill> --tool <operation> --params '{...}'
npm run mcp:test -- <skill> --verbose
```

## Repos

- **This repo** (`agentos-community`) — skills, shapes, docs. YAML + Python.
- **Engine repo** (`agentos`) — Rust engine, graph, MCP bridge. You don't need to touch Rust to write skills.
