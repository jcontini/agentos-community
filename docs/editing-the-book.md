# Editing This Book

This chapter is for **maintainers** — humans and agents who change the Skill Book or reverse-engineering guides. The Skill Book is our **internal knowledge store**: contract for skills, operational playbooks, and methodology we expect every contributor (and every future session) to rely on.

---

## Before you edit anything

1. Read the **[Introduction](intro.md)** through once — it orients repos, audiences, and where to look next.
2. Skim **`docs/SUMMARY.md`** (the table of contents mdBook uses). On the [published site](https://jcontini.github.io/agentos-community/), that is the sidebar. You should know what already exists so you do not duplicate or contradict it.
3. If your change affects skill contracts or validation, follow the **Contributing** section in the repo **`README.md`** and run the checks it lists (`npm run validate`, `mcp:test`, etc.).

---

## Tooling

| Goal | Command |
|------|---------|
| Local preview with reload | `mdbook serve` (opens a local server; default port 3000) |
| One-shot build | `mdbook build` — output in `target/book/` |
| CI / GitHub Pages | Workflow `.github/workflows/book.yml` runs `mdbook build` on pushes that touch `docs/**` or `book.toml` |

Config lives in **`book.toml`** at the repo root. Chapter sources live under **`docs/`**; navigation order is **`docs/SUMMARY.md`** only — a file not linked from `SUMMARY.md` is omitted from the built book.

---

## Linking rules (mdBook)

- Use **`.md` paths in source** for pages inside this book (e.g. `[Auth](skills/connections.md)`). mdBook rewrites them to `.html` in `target/book/`.
- **Do not hand-author `.html` links** in markdown — they break GitHub’s markdown preview and confuse local editing.
- **Chapter files in a folder:** name the main file **`index.md`**, not `README.md`. mdBook emits `index.html` for `README.md` sources but still rewrites markdown links to `README.html`, which **does not exist** — readers get a broken page (often without book chrome/CSS). This is a [long-standing mdBook limitation](https://github.com/rust-lang/mdBook/issues/984). The reverse-engineering layers use `index.md` for that reason.
- **Anchor links** work in source as `page.md#section-id` and carry through to the built HTML.
- **Paths outside `docs/`** (e.g. `skills/exa/readme.md`) are not part of the book build; those links are for people browsing the repo on GitHub. On the static site they may not resolve — prefer linking to the GitHub tree URL when the audience is web readers.

---

## What to update when you change the product

| Change | Also update |
|--------|-------------|
| New or renamed skill | [Skill Catalog](catalog.md), skill `readme.md`, and any chapter that lists examples |
| Auth / credential behavior | [Auth Flows](skills/auth-flows.md), [Connections & Auth](skills/connections.md), relevant [reverse engineering](reverse-engineering/overview.md) sections |
| New reverse-engineering methodology | Appropriate layer under `docs/reverse-engineering/` — keep cross-links between layers consistent |
| Contract / schema / lint rules | [Skill Anatomy](skills/anatomy.md), [Operations](skills/operations.md), [Testing](skills/testing.md), and repo validation docs |

Ship doc updates **in the same change** as behavior when possible. Stale docs cost the next person (or the next agent) more than missing docs.

---

## Style

- Prefer **examples over theory** — link to real skills (`skills/exa/`, `skills/kitty/`, etc.).
- Prefer **short sections** with clear headings so deep links stay stable.
- **Skill readmes** (`skills/<name>/readme.md`) are living docs; keep them aligned with the YAML and code.

When in doubt, add a link from [Introduction](intro.md) or this chapter so the next editor finds your material.
