# AgentOS Community — Agent Guide

> Read this first. It gives you orientation and operational patterns for contributing to this repo.

---

## First: Check Skills

**Before starting work, check if there's a relevant skill:**

```bash
ls skills/
```

Skills contain detailed guidance for specific tasks. If the user asks you to do something that matches a skill, **read the skill first** before proceeding.

| Skill | When to Use |
|-------|-------------|
| `write-adapter.md` | Creating or modifying skills |
| `write-app.md` | Writing apps or entity components |
| `shell-history.md` | Querying shell history |
| `apple-biome.md` | Screen time, app usage, media playback, location, device activity |

---

## Second: Read CONTRIBUTING.md

**CONTRIBUTING.md is the source of truth** for skill structure, entity schemas, component rules, and testing. Read it before making changes.

This file (AGENTS.md) adds agent-specific workflow guidance.

---

## What This Repo Is

**The AgentOS ecosystem.** Everything lives here — skills, entities, apps, themes, and components.

- **Core repo** (`agentos`) — the Rust/React engine (generic, knows nothing about specific entities or services)
- **This repo** (`agentos-community`) — all content: skills, entities, apps (including system apps), themes

**In development, the server points directly at this repo** (`~/dev/agentos-community`). Edits here are live after a server restart. Core embeds a snapshot at build time for fresh installs; the community version overrides the bundled copy.

**Three concerns, one home:**

| Concern | Directory | What it is |
|---------|-----------|-----------|
| **Entities** | `entities/` | The Memex model — what things ARE |
| **Skills** | `skills/` | The capability layer — service connections + agent instructions |
| **Apps** | `apps/` | The visual layer — UI experiences (optional) |

---

## Key Directories

| Path | Purpose |
|------|---------|
| `skills/` | Skills — service connections + agent context (API bindings + guides) |
| `entities/` | Entity schemas — the Memex model |
| `apps/` | Visual apps — UI experiences (Videos, Browser, Settings, etc.) |
| `themes/` | Visual styling (CSS) |
| `agents/` | Setup instructions for AI clients (Cursor, Claude, etc.) |
| `tests/` | Test utilities and fixtures |
| `scripts/` | Manifest generation, setup scripts |

### Skill Organization

```
skills/
  todoist/           # Top-level for common skills
  linear/
  exa/
  apple-calendar/    # Native macOS integrations
  write-adapter.md   # Guide skills (markdown, no API binding)
  shell-history.md
  .needs-work/       # Skills that need completion
    communication/
    databases/
    government/
```

---

## Development Workflow

**Edit directly in this repo.** The server's `sources` setting points here (`~/dev/agentos-community`). There is no separate `~/.agentos/installed/` folder — do NOT create one.

```bash
# 1. Edit directly in the community repo (this is the live source)
vim ~/dev/agentos-community/skills/reddit/readme.md

# 2. Restart AgentOS server and test
cd ~/dev/agentos && ./restart.sh
curl -X POST http://localhost:3456/api/skills/reddit/post.list \
  -d '{"subreddit": "programming", "limit": 1}'

# 3. Validate and commit
cd ~/dev/agentos-community
npm run validate
git add -A && git commit -m "Update Reddit skill"
```

**Why this workflow:**
- This repo IS the live source — no copy step, no installed folder
- Changes take effect on server restart
- Everything stays in version control

---

## Commands

```bash
npm run validate              # Schema validation + test coverage (run first!)
npm test                      # Functional tests (excludes .needs-work)
npm run test:needs-work       # Test skills in .needs-work
npm test skills/exa/tests     # Test specific skill
```

### Validation vs Tests

| Command | What it checks |
|---------|----------------|
| `npm run validate` | Schema structure, test coverage, required files (icon.svg) |
| `npm test` | Actually calls APIs, verifies behavior |

**Always run `npm run validate` first** — it catches structural issues before you test functionality.

---

## Skill Checklist

Before committing a skill:

- [ ] `icon.svg` or `icon.png` exists
- [ ] `npm run validate` passes
- [ ] Mapping covers entity properties (check `entities/{entity}.yaml`)
- [ ] Functional tests pass (`npm test`)

## Expression Syntax

Skills use **jaq expressions** (jq syntax), not template strings:

```yaml
# Correct — jaq expressions
url: '"https://api.example.com/tasks/" + .params.id'
query:
  limit: .params.limit | tostring
  priority: 5 - .params.priority

# Wrong — old template syntax
url: "https://api.example.com/tasks/{{params.id}}"
```

**Common patterns:**
- String concat: `'"https://example.com/" + .params.id'`
- To string: `.params.limit | tostring`
- URL encode: `.params.query | @uri`
- Unix -> ISO: `.created_utc | todate`
- Optional: `.due.date?`
- Conditional: `'if .params.x == "y" then "a" else "b" end'`

See CONTRIBUTING.md for detailed skill structure, adapters, executors, and transforms.

---

## Entity Components

**Components must only compose primitives — never custom CSS.**

```tsx
// Good: uses data-* attributes for styling
<div data-component="stack" data-direction="horizontal" data-gap="md">
  <span data-component="text" data-variant="title">{title}</span>
</div>

// Bad: custom CSS that breaks themes
<div style={{ display: 'flex', gap: '16px' }}>
  <span className="my-title">{title}</span>
</div>
```

**Why:** Themes style primitives via `[data-component="text"]` selectors. Custom CSS breaks theming.

**Image proxy:** External images need proxying to bypass hotlink protection:

```tsx
function getProxiedSrc(src: string | undefined): string | undefined {
  if (!src) return undefined;
  if (src.startsWith('/') || src.startsWith('data:') || src.startsWith('blob:')) return src;
  return `/api/proxy/image?url=${encodeURIComponent(src)}`;
}
```

See CONTRIBUTING.md for full component guidelines.

---

## The `.needs-work` Folder

Skills that fail validation live in `skills/.needs-work/`:

- Missing `icon.svg`
- Schema validation errors
- Missing tests for operations

**To fix a skill:**
1. Fix the issues
2. Run `npm run validate`
3. Move to working folder: `mv skills/.needs-work/my-skill skills/my-skill`

---

## Manifest

**Never edit `manifest.json` manually!**

GitHub Actions auto-generate it on push to `main`. To test locally:

```bash
node scripts/generate-manifest.js        # Regenerate
node scripts/generate-manifest.js --check  # Validate only
```

---

## Key Files

| File | Purpose |
|------|---------|
| `CONTRIBUTING.md` | Complete technical reference — skill structure, entities, components |
| `tests/skills/skill.schema.json` | Schema source of truth for skill YAML |
| `tests/utils/fixtures.ts` | Test utilities (`aos()` helper) |
| `entities/{entity}.yaml` | Entity schema — what properties to map |
