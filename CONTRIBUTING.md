# Contributing to the AgentOS Community

Declarative YAML for entities, plugins, components, apps, and themes.

**Schema reference:** `tests/plugins/plugin.schema.json` — the source of truth for plugin structure.

**Using an AI agent?** Have it read `AGENTS.md` for operational guidance and workflow patterns.

---

## Development Workflow

**Recommended:** Develop in `~/.agentos/installed/`, then copy here when ready.

```bash
# 1. Edit directly in installed folder (fast iteration)
vim ~/.agentos/installed/plugins/reddit/readme.md

# 2. Restart server and test
cd ~/dev/agentos && ./restart.sh
curl -X POST http://localhost:3456/api/plugins/reddit/post.list \
  -d '{"subreddit": "programming", "limit": 1}'

# 3. When working, copy to community repo
cp -r ~/.agentos/installed/plugins/reddit ~/dev/agentos-community/plugins/

# 4. Validate and commit
cd ~/dev/agentos-community
npm run validate
git add -A && git commit -m "Update Reddit plugin"
```

---

## 🎉 Manifest Auto-Generates!

**Never edit `manifest.json` manually!** 

GitHub Actions automatically scans the repo on push to `main`, reads YAML front matter, and generates an updated manifest.

```bash
# Test locally
node scripts/generate-manifest.js        # Regenerate
node scripts/generate-manifest.js --check # Validate only
```

---

## Architecture Overview

**Key insight: Apps contain models.** Apps define models (data schema), views, and components. Plugins are adapters that map external APIs to these models.

```
apps/              Self-contained app packages
  tasks/           models.yaml + icon.png + components/
  posts/           models.yaml + icon.png + components/
  domains/         models.yaml (domain entity + dns_record model)

plugins/           Adapters (how services map to app models)
  reddit/          Maps Reddit API → post model
  todoist/         Maps Todoist API → task model
  porkbun/         Maps Porkbun API → domain model

themes/            Visual styling (CSS)
```

**The flow:** 
1. Plugins declare which models they provide (via `adapters:` section)
2. Apps define models + views + components
3. Apps with `show_as_app: true` appear on the desktop when plugins support them

---

## Writing Plugins

**For detailed plugin writing guidance, read the skill:**

```bash
~/.agentos/drive/skills/write-plugin.md
```

This covers:
- Entity reuse patterns (use existing entities before creating new ones)
- Entity-level utilities (e.g., `domain.dns_list` for DNS operations)
- Adapters and mappings
- Expression syntax (jaq)
- Testing requirements

### Quick Reference

**Plugin structure:**
```
plugins/{name}/
  readme.md     # YAML front matter + docs
  icon.svg      # Required
  tests/        # Functional tests
```

**Operations return types:** `entity`, `entity[]`, or `void`

**Entity-level utilities:** Name as `entity.utility_name` (e.g., `domain.dns_list`, not `dns_record.list`)

---

## Writing Apps

**For detailed app writing guidance, read the skill:**

```bash
~/.agentos/drive/skills/write-app.md
```

### Quick Reference

**App structure:**
```
apps/{app}/
  models.yaml     # Entity definitions + views
  icon.png        # Desktop icon (PNG preferred)
  components/     # TSX components
```

**Models can define:**
- `properties:` — Entity schema
- `operations:` — Standard CRUD (`[list, get, create, update, delete]`)
- `utilities:` — Entity-level helpers with custom return shapes
- `display:` — How to show in UI (`show_as_app: true` for desktop apps)

---

## Components

App components live in `apps/{app}/components/`. They compose framework primitives — never custom CSS.

**Key rules:**
- Use `data-*` attributes: `data-component="text" data-variant="title"`
- Proxy external images with `getProxiedSrc()`
- Export default: `export default MyComponent`

**See examples:** `apps/posts/components/`, `apps/groups/components/`

---

## Testing

```bash
npm run validate              # Schema + test coverage (run first!)
npm test                      # Functional tests
npm test plugins/exa/tests    # Single plugin
```

**Validation checks:** Schema structure, test coverage, required files (icon).

**`.needs-work/`** — Plugins that fail validation are auto-moved here.

**Every operation needs at least one test.** Include `tool: "operation.name"` references even in skipped tests.

---

## Commands

```bash
npm run new-plugin <name>    # Create plugin scaffold
npm run validate             # Schema validation (run first!)
npm test                     # Functional tests
```

---

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.
