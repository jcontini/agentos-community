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
| [Python Skills](skills/python.md) | Python executor, `_call` dispatch, shape-native returns |
| [Auth Flows](skills/auth-flows.md) | Login flows, `__secrets__`, Playwright→HTTPX |
| [Data & Storage](skills/data.md) | Sandbox storage, expressions, secret store |
| [Views & Output](skills/views.md) | Preview/full/JSON output contract |
| [Testing](skills/testing.md) | MCP testing, smoke metadata, checklist |
| [Reverse Engineering](reverse-engineering/overview.md) | 7-layer playbook for services without public APIs |
| [Helper Files & Patterns](skills/reference.md) | Leading examples, advanced patterns |
| [Skill Catalog](catalog.md) | All available skills by category |
| [Editing This Book](editing-the-book.md) | How to maintain this book — tooling, links, mdBook quirks |

## Internal knowledge store

This repository’s **`docs/`** tree is the **Skill Book** — our shared playbook for building skills, testing them, and reverse-engineering services when there is no clean public API. Treat it like an internal wiki: if you learn something durable, it belongs here. Maintainer-focused workflow (build commands, linking rules, what to update when) lives in **[Editing This Book](editing-the-book.md)**.

## Two repos

- **[agentOS-core](https://github.com/jcontini/agentOS-core)** (private) — the Rust engine, core graph, MCP bridge, credential store, process architecture. You only need this if you're hacking on the engine itself.
- **[agentos-community](https://github.com/jcontini/agentos-community)** (this repo, public) — skills, skill documentation, reverse engineering guides, and this book. Anyone can contribute skills without touching Rust.

## For AI agents

**Start here every session:** read this introduction in full, then read **`docs/SUMMARY.md`** (the table of contents) so you know what chapters exist and where topics live. On the [published book](https://jcontini.github.io/agentos-community/), that is the sidebar — use it before searching at random.

Then read [Skill Anatomy](skills/anatomy.md) and follow links for your task. The [Testing](skills/testing.md) chapter covers `mcp:call` and `mcp:test` — use those to verify your changes. If you are editing the book itself, read [Editing This Book](editing-the-book.md) first.

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

- **Links:** Use `.md` paths for pages inside this book; mdBook rewrites them to `.html` in the build output. Do not hand-author `.html` URLs in markdown. For a **chapter’s main file in a subdirectory**, use **`index.md`** (not `README.md`) — mdBook maps `README.md` to `index.html` but still rewrites links to `README.html`, which breaks navigation on GitHub Pages. See [Editing This Book](editing-the-book.md).
- **Examples over theory.** Point to real skill implementations. A working `exa.py` teaches more than a paragraph of explanation.
- **Show your work.** When reverse engineering, document what you tried, what worked, and what didn't. The next agent hitting the same service will thank you.
- **Skill readmes are living docs.** Each skill's `readme.md` should reflect the current state of the implementation — auth flow, known endpoints, gotchas, and next steps.
