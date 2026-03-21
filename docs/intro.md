# AgentOS Skills

> **You are reading the Skill Book** — the guide for building, testing, and contributing skills for AgentOS.
> For engine architecture and Rust internals → see the [core repo](https://github.com/jcontini/agentos).
> For the project vision and philosophy → see the core repo's Project Book.
>
> **Open in browser:** `open target/book/index.html` (after `mdbook build`)

---

## Chapters

| Chapter | What it covers |
|---------|---------------|
| [Setup & Workflow](getting-started.md) | Clone, install, validate, test |
| [Skill Anatomy](skills/anatomy.md) | Folder shape, skill.yaml, entity vs local control |
| [Operations](skills/operations.md) | Operations, actions, capabilities (`provides:`) |
| [Connections & Auth](skills/connections.md) | API keys, cookies, OAuth, providers |
| [Adapters](skills/adapters.md) | Canonical fields, entity mapping, relationships |
| [Python Skills](skills/python.md) | Python executor, `_call` dispatch |
| [Auth Flows](skills/auth-flows.md) | Login flows, `__secrets__`, Playwright→HTTPX |
| [Data & Storage](skills/data.md) | Sandbox storage, expressions, secret store |
| [Views & Output](skills/views.md) | Preview/full/JSON output contract |
| [Testing](skills/testing.md) | MCP testing, smoke metadata, checklist |
| [Reverse Engineering](reverse-engineering/overview.md) | 7-layer playbook for services without public APIs |
| [Helper Files & Patterns](skills/reference.md) | Leading examples, advanced patterns |
| [Skill Catalog](catalog.md) | All available skills by category |

## Two repos

- **[agentos](https://github.com/jcontini/agentos)** (private) — the Rust engine, core graph, MCP bridge, credential store, process architecture. You only need this if you're hacking on the engine itself.
- **[agentos-community](https://github.com/jcontini/agentos-community)** (this repo, public) — skills, skill documentation, reverse engineering guides, and this book. Anyone can contribute skills without touching Rust.

## For AI agents

Read [Skill Anatomy](skills/anatomy.md) first, then follow the links for your task. The [Testing](skills/testing.md) chapter covers `mcp:call` and `mcp:test` — use those to verify your changes.
