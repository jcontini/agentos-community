# Contributing to AgentOS Community

Everything lives here — entities, skills, apps, and themes. Core (`agentos`) is a generic Rust engine; this repo is the ecosystem.

In development, the server points directly at this repo (`~/dev/agentos-community`). Edits are live after a server restart. Core embeds a snapshot at build time; the community version overrides it.

| Concern | Directory | What it is |
|---------|-----------|-----------|
| **Entities** | `entities/` | The Memex model — what things ARE |
| **Skills** | `skills/` | Service connections + agent instructions |
| **Apps** | `apps/` | UI experiences (Videos, Memex, Settings, etc.) |
| **Themes** | `themes/` | Visual styling (CSS) |

---

## Guide Skills

Read the relevant guide before starting work:

| Guide | When to Use |
|-------|-------------|
| `skills/write-skill.md` | **Default.** Writing, updating, or fixing skills |
| `skills/write-app.md` | Writing apps or entity components |
| `skills/shell-history.md` | Querying shell history |
| `skills/apple-biome.md` | Screen time, app usage, media playback, location |

**`write-skill.md` is the comprehensive one** — structure, executors, transformers, testing, entity reuse, live data on available models and existing adapters.

---

## Quick Start

```bash
# 1. Edit directly in this repo (it's the live source)
vim skills/my-skill/readme.md

# 2. Restart AgentOS server and test
cd ~/dev/agentos && ./restart.sh
curl http://localhost:3456/mem/tasks?skill=my-skill

# 3. Validate and commit
npm run validate
git add -A && git commit -m "Add my-skill"
```

---

## Commands

```bash
npm run validate             # Schema validation + test coverage (run first!)
npm test                     # Functional tests (excludes .needs-work)
npm run test:needs-work      # Test skills in .needs-work
npm test skills/exa/tests    # Test specific skill
npm run new-skill <name>     # Create skill scaffold
```

| Command | What it checks |
|---------|----------------|
| `npm run validate` | Schema structure, test coverage, required files (icon.svg) |
| `npm test` | Actually calls APIs, verifies behavior |

**Always run `npm run validate` first** — it catches structural issues before you test.

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

**Image proxy:** External images need proxying to bypass hotlink protection. Import the shared helper:

```tsx
import { getProxiedSrc } from '/ui/lib/utils.js';

// getProxiedSrc handles data:, blob:, protocol-relative, and external URLs
// External URLs are rewritten to /ui/proxy/image?url=...
<img src={getProxiedSrc(item.thumbnail)} />
```

---

## The `.needs-work` Folder

Skills that fail validation live in `skills/.needs-work/`. To fix one:

1. Fix the issues
2. Run `npm run validate`
3. Move to working folder: `mv skills/.needs-work/my-skill skills/my-skill`

---

## Manifest

**Never edit `manifest.json` manually!** GitHub Actions auto-generate it on push to `main`.

```bash
node scripts/generate-manifest.js        # Regenerate
node scripts/generate-manifest.js --check # Validate only
```

---

## Key Files

| File | Purpose |
|------|---------|
| `tests/skills/skill.schema.json` | Schema source of truth for skill YAML |
| `tests/utils/fixtures.ts` | Test utilities (`aos()` helper) |
| `entities/{entity}.yaml` | Entity schema — what properties to map |

---

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.
