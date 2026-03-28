# Development Process

How we plan, design, build, and document things in AgentOS.

## Spec files

A spec file captures design thinking for a specific system or feature. Specs live in `docs/specs/` alongside the rest of the book — they're ephemeral working documents that get deleted when the work ships.

### Lifecycle

Each spec file lives through four stages, then dies:

1. **Design** — problem, domain model, principles, phasing. The file is a conversation about what to build and why.
2. **Build guide** — the active phase gets expanded into step-by-step implementation detail (file plan, code, tests). A developer agent can execute it without additional context.
3. **Tracker** — as phases ship, collapse the build guide into a "Done" summary. Expand the next phase into its build guide.
4. **Delete** — when the last phase ships, delete the spec. Before deletion, update any docs that reference it (roadmap, Skill Book in `agentos-community/docs/`, README) so links don't go stale.

No spec is permanent. No spec splits into multiple files for the same system. One file, one lifecycle.

### Writing a spec

A good spec answers:

- **What's the problem?** What's broken or missing today, in concrete terms.
- **What's the design?** The structural changes — schema, code, contract — that fix it.
- **What are the phases?** Independent, shippable chunks ordered by dependency.
- **What's the behavioral before/after?** For each phase: what can an agent or user do after this phase ships that they couldn't before? This is the test. Success is not "we updated these files" — it's "the system now behaves differently in this observable way."

### Referencing specs

The [roadmap](../specs/_roadmap.md) links to active specs by path (e.g. `docs/specs/done/credential-system.md`). Specs link back to the roadmap for sequencing context. When a spec is deleted, the roadmap entry gets a strikethrough and a "Done" summary.

## Roadmap Discipline

The live roadmap is `docs/specs/_roadmap.md`.

Keep it simple:

- exactly one `Current`
- exactly one `Next`
- concise `Done`
- everything else in `Backlog`

Rules:

- `Current` is the only thing an agent should advance without reprioritizing.
- `Next` is the single queued follow-up and should usually be unblocked by `Current`.
- `Backlog` items are not ordered promises. They are options with triggers.
- When `Current` ships, update the roadmap in the same turn: move it to `Done`, promote `Next`, and choose a new `Next` or leave it empty on purpose.

## Documentation layers

AgentOS uses a three-layer documentation system:

| # | Surface | What belongs there | How to read |
|---|---------|-------------------|-------------|
| 1 | **README** | Agent bootstrap — mandatory reads, principles, quick reference | Open `README.md` |
| 2 | **Project book** (mdBook) | Vision, principles, operations, design decisions, development process | `mdbook serve docs/book` |
| 3 | **Code docs** (`cargo doc`) | Architecture, APIs, data model, module guides, verified examples | `cargo doc --workspace --no-deps --open` |

The placement rule:

| Content | Where it lives |
|---------|---------------|
| How the code works | `///` and `//!` in Rust source (layer 3) |
| How we work together (process, principles, operations) | This book or README (layers 1–2) |
| Live priorities and sequencing | `docs/specs/_roadmap.md` |
| Active design/build specs (ephemeral) | `docs/specs/` — the roadmap links to them |
| How to build skills (authoring guides, reverse engineering) | `agentos-community/` docs |

If you're documenting an API or module, edit Rust doc comments — not the book. If you're documenting process, philosophy, or project decisions, edit the book — not code comments.

## Cross-repo documentation

| Repo | Docs | Audience |
|------|------|----------|
| `agentos` | This book + `cargo doc` + `spec/` | Project contributors, agents working on core |
| `agentos-community` | **Skill Book** (`docs/`) | Skill authors, agents building or debugging skills |

The community repo's **Skill Book** (mdBook, source in `docs/`, `mdbook build && open target/book/index.html`) is the canonical skill-authoring contract — adapter conventions, canonical field names, operation naming rules, connections, auth flows, testing. The book also includes the reverse engineering guides (transport, discovery, auth, content, social, desktop apps, MCP). Entrypoint: `docs/intro.md`; maintainer workflow: `docs/editing-the-book.md`.

When core changes affect the skill contract (e.g. new canonical fields, storage behavior changes), update the Skill Book in the community repo as part of the same work.

## Verification

After each phase of spec work (or any commit-worthy chunk): run checks, verify MCP end-to-end, then commit. See [Testing](../operations/testing.md) for the full phase completion checklist.
