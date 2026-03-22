# AgentOS Skills

> **You are reading the Skill Book** — the guide for building, testing, and contributing skills for AgentOS.
> For engine architecture and Rust internals → see the [core repo](https://github.com/jcontini/agentOS-core).
> For the project vision and philosophy → see the core repo's Project Book.

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

- **[agentOS-core](https://github.com/jcontini/agentOS-core)** (private) — the Rust engine, core graph, MCP bridge, credential store, process architecture. You only need this if you're hacking on the engine itself.
- **[agentos-community](https://github.com/jcontini/agentos-community)** (this repo, public) — skills, skill documentation, reverse engineering guides, and this book. Anyone can contribute skills without touching Rust.

## For AI agents

Read [Skill Anatomy](skills/anatomy.md) first, then follow the links for your task. The [Testing](skills/testing.md) chapter covers `mcp:call` and `mcp:test` — use those to verify your changes.

## Maintaining these docs

These docs are built by agents, for agents. Every future session that reads
this book benefits from the clarity you leave behind — and suffers from the
gaps you don't fill. Pay it forward.

**When you learn something, write it down.**

- Discovered a new auth pattern? Add it to the [reverse engineering guide](reverse-engineering/overview.md).
- Found a gotcha with a tool? Document it where the next agent will look.
- Built a new skill? Update the [catalog](catalog.md) and link to it from relevant docs.
- Changed how something works? Update the doc in the same session. Stale docs are worse than no docs.

**Conventions:**

- **Links:** Always use `.md` extensions for internal links (e.g. `[Auth](./README.md)`). mdbook converts them to `.html` automatically during build. Never link to `.html` — those paths don't exist until build time and break local preview, GitHub rendering, and AI navigation.
- **Examples over theory.** Point to real skill implementations. A working `exa.py` teaches more than a paragraph of explanation.
- **Show your work.** When reverse engineering, document what you tried, what worked, and what didn't. The next agent hitting the same service will thank you.
- **Skill readmes are living docs.** Each skill's `readme.md` should reflect the current state of the implementation — auth flow, known endpoints, gotchas, and next steps.
