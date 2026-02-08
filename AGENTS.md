# AgentOS Community — Agent Guide

> Read this first. It gives you orientation and operational patterns for contributing to this repo.

---

## First: Check Skills

**Before starting work, check if there's a relevant skill:**

```bash
ls ~/.agentos/drive/skills/
```

Skills contain detailed guidance for specific tasks. If the user asks you to do something that matches a skill, **read the skill first** before proceeding.

| Skill | When to Use |
|-------|-------------|
| `write-adapter.md` | Creating or modifying adapters |

---

## Second: Read CONTRIBUTING.md

**CONTRIBUTING.md is the source of truth** for adapter structure, entity schemas, component rules, and testing. Read it before making changes.

This file (AGENTS.md) adds agent-specific workflow guidance.

---

## What This Repo Is

**Community content for AgentOS** — adapters, entities, themes, and components that users install via the App Store.

- **Core repo** (`agentos`) — the Rust/React app itself
- **This repo** (`agentos-community`) — installable content

When users click "Install" in the AgentOS App Store, it downloads from this repo to `~/.agentos/installed/`.

---

## Key Directories

| Path | Purpose |
|------|---------|
| `adapters/` | Service adapters (Reddit → post, YouTube → video, etc.) |
| `entities/` | Entity schemas + views + components (apps spawn from entities at runtime) |
| `skills/` | Workflow guides (how to use entities for specific domains) |
| `themes/` | Visual styling (CSS) |
| `agents/` | Setup instructions for AI clients (Cursor, Claude, etc.) |
| `tests/` | Test utilities and fixtures |
| `scripts/` | Manifest generation, setup scripts |

### Adapter Organization

Adapters are organized by category:

```
adapters/
  todoist/           # Top-level for common adapters
  linear/
  exa/
  apple-calendar/    # Native macOS integrations
  .needs-work/       # Adapters that need completion
    communication/
    databases/
    government/
```

---

## Development Workflow

**Recommended:** Edit in `~/.agentos/installed/`, test with running server, copy here when ready.

```bash
# 1. Edit directly in installed folder (fast iteration)
vim ~/.agentos/installed/adapters/reddit/readme.md

# 2. Restart AgentOS server and test
cd ~/dev/agentos && ./restart.sh
curl -X POST http://localhost:3456/api/adapters/reddit/post.list \
  -d '{"subreddit": "programming", "limit": 1}'

# 3. When working, copy to community repo
cp -r ~/.agentos/installed/adapters/reddit ~/dev/agentos-community/adapters/

# 4. Validate and commit
cd ~/dev/agentos-community
npm run validate
git add -A && git commit -m "Update Reddit adapter"
```

**Why this workflow:**
- Changes in `~/.agentos/installed/` take effect on server restart
- No copy step between edits — fast feedback
- Community repo stays clean — only tested code gets committed

---

## Commands

```bash
npm run validate              # Schema validation + test coverage (run first!)
npm test                      # Functional tests (excludes .needs-work)
npm run test:needs-work       # Test adapters in .needs-work
npm test adapters/exa/tests    # Test specific adapter
```

### Validation vs Tests

| Command | What it checks |
|---------|----------------|
| `npm run validate` | Schema structure, test coverage, required files (icon.svg) |
| `npm test` | Actually calls APIs, verifies behavior |

**Always run `npm run validate` first** — it catches structural issues before you test functionality.

---

## Adapter Checklist

Before committing a adapter:

- [ ] `icon.svg` or `icon.png` exists
- [ ] `npm run validate` passes
- [ ] Mapping covers entity properties (check `entities/{group}/{entity}.yaml`)
- [ ] Functional tests pass (`npm test`)

## Expression Syntax

Adapters use **jaq expressions** (jq syntax), not template strings:

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
- Unix → ISO: `.created_utc | todate`
- Optional: `.due.date?`
- Conditional: `'if .params.x == "y" then "a" else "b" end'`

See CONTRIBUTING.md for detailed adapter structure, adapters, executors, and transforms.

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

Adapters that fail validation are moved to `adapters/.needs-work/`:

- Missing `icon.svg`
- Schema validation errors
- Missing tests for operations

**To fix a adapter:**
1. Fix the issues
2. Run `npm run validate`
3. Move to working folder: `mv adapters/.needs-work/my-adapter adapters/my-adapter`

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
| `CONTRIBUTING.md` | Complete technical reference — adapter structure, entities, components |
| `tests/adapters/adapter.schema.json` | Schema source of truth for adapter YAML |
| `tests/utils/fixtures.ts` | Test utilities (`aos()` helper) |
| `entities/{group}/{entity}.yaml` | Entity schema — what properties to map |
