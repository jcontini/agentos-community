# AgentOS Community

Community skills and skill docs for [AgentOS](https://github.com/jcontini/agentOS-core).

---

## Before you do anything else (humans and agents)

This repo’s **Skill Book** (`docs/`) is our **internal knowledge store** for how skills work and how we reverse-engineer services. **Read the landing page and the full table of contents before** you edit skills, run validation, or open a PR:

- **Published:** [jcontini.github.io/agentos-community](https://jcontini.github.io/agentos-community/) — start at *Introduction*, then scan every section in the sidebar (same order as `docs/SUMMARY.md`).
- **In-repo:** open [`docs/intro.md`](docs/intro.md), then [`docs/SUMMARY.md`](docs/SUMMARY.md).

Maintainers: after that, read **[Editing This Book](docs/editing-the-book.md)** for mdBook commands, linking rules, and what to update when the contract changes.

---

## What is AgentOS?

**AgentOS is the semantic layer between AI assistants and your digital life.**

Your tasks are in Todoist. Your calendar is in Google. Your messages are split across iMessage, WhatsApp, Slack. Your files are everywhere. Each service is a walled garden—they don't talk to each other, and switching is painful.

**AgentOS fixes this.** It gives AI assistants a unified way to access all your services through a universal language. Your AI can manage tasks, read your calendar, send messages, and search the web—all through one interface, regardless of which service you use.

### The Vision

**You should own your digital life.** Not rent it. Not have it held hostage. Own it.

AgentOS creates a universal entity model—tasks, events, contacts, messages, files—that works across all services. A Todoist skill maps Todoist's API to the universal `task` entity. A Linear skill does the same. From your AI's perspective, they're identical: `list_tasks()`, `create_task()`, `complete_task()`.

This means:
- **Migration is trivial** — Switch from Todoist to Linear? Same entity, different backend
- **Cross-service queries work** — "Show tasks due today from all sources"
- **AI understands everything** — One schema, not 50 proprietary formats
- **You're in control** — Your data, your computer, your rules

### How It Works

```
┌──────────────────────────────────────────────────────────────┐
│                         YOUR SERVICES                        │
│    Todoist · Linear · Reddit · YouTube · Calendar · iMessage │
└──────────────────────────────┬───────────────────────────────┘
                               │ APIs
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                           SKILLS                             │
│  YAML configs: API endpoints, auth, field mappings (jaq)     │
│  One line routes content to body table: content: .content    │
└──────────────────────────────┬───────────────────────────────┘
                               │ extract
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     ENTITY GRAPH (SQLite)                     │
│  tasks · people · messages · videos · webpages · documents   │
│  + FTS5 full-text search across all content (BM25 ranking)   │
└──────────────────────────────┬───────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
         ┌───────────┐   ┌─────────────┐
         │  HTTP API │   │  MCP (AI)   │
         │  (REST)   │   │  (agents)   │
         └───────────┘   └─────────────┘
```

---

## What's Here

```
book.toml          Skill Book config (mdBook)
docs/              Skill Book chapters + reverse engineering guides
skills/            Skills — YAML configs + Python/bash/Swift helpers
```

Skills are YAML configurations with optional helper scripts. The Rust engine is a generic runtime — you don't need to understand Rust to write skills. Browse `skills/` for all available skills, or see the [Skill Catalog](docs/catalog.md) for a categorized directory.

---

## Skill Book

The **Skill Book** is the complete guide for building, testing, and contributing skills. Read it online at **[jcontini.github.io/agentos-community](https://jcontini.github.io/agentos-community/)**, or browse the source files directly in `docs/`:

| Topic | Chapter |
|-------|---------|
| Setup, workflow, validation | [Getting Started](docs/getting-started.md) |
| skill.yaml structure | [Skill Anatomy](docs/skills/anatomy.md) |
| Operations, actions, capabilities | [Operations](docs/skills/operations.md) |
| Connections, auth, cookies, OAuth | [Connections & Auth](docs/skills/connections.md) |
| Entity field mappings | [Adapters](docs/skills/adapters.md) |
| Python executor, `_call` dispatch | [Python Skills](docs/skills/python.md) |
| Login flows, `__secrets__` | [Auth Flows](docs/skills/auth-flows.md) |
| Sandbox storage, expressions | [Data & Storage](docs/skills/data.md) |
| MCP testing, smoke metadata | [Testing](docs/skills/testing.md) |
| Reverse engineering web services | [Reverse Engineering](docs/reverse-engineering/overview.md) |

**Canonical examples:** `skills/exa/` (entity-returning) and `skills/kitty/` (local-control/action).

When you change the skill contract, **update the book in the same change**.

---

## Contributing

**Anyone can contribute.** Found a bug? Want a new skill? Have an idea? [Open an issue](https://github.com/jcontini/agentos-community/issues).

```bash
git clone https://github.com/jcontini/agentos-community
cd agentos-community
npm install    # sets up pre-commit hooks
```

Useful commands:

```bash
npm run validate -- exa
npm run lint:semantic -- exa
npm run mcp:call -- --skill exa --tool search --params '{"query":"rust","limit":1}'
npm run mcp:test -- exa --verbose
```

---

## License

**MIT** — see [LICENSE](LICENSE).

By contributing, you grant AgentOS the right to use your contributions in official releases, including commercial offerings. Your code stays open forever.
