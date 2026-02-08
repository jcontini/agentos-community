# Contributing to the AgentOS Community

Declarative YAML for entities, adapters, components, apps, and themes.

**Schema reference:** `tests/adapters/adapter.schema.json` — the source of truth for adapter structure.

**Using an AI agent?** Have it read `AGENTS.md` for operational guidance and workflow patterns.

---

## Development Workflow

**Recommended:** Develop in `~/.agentos/installed/`, then copy here when ready.

```bash
# 1. Edit directly in installed folder (fast iteration)
vim ~/.agentos/installed/adapters/reddit/readme.md

# 2. Restart server and test
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

**Skills are the single source of truth for entity types.** Want a new entity type? Add a skill YAML file. That's it. The skill defines:

- **Schema** — properties, types, validation
- **Relationships** — what this entity connects to (via properties or relationships table)
- **Display** — how it appears in UI, whether it shows as an app
- **Views** — TSX components for rendering

Adapters are adapters that map external APIs to these entity types. No hardcoded types anywhere.

```
entities/          Entity type definitions (single source of truth)
  tasks/           task.yaml, project.yaml, label.yaml + icon.png + views/
  discussion/      post.yaml + icon.png + views/
  messaging/       message.yaml, conversation.yaml + views/
  people/          person.yaml + views/

skills/            Workflow guides (how to use entities for specific domains)
  roadmap/         skill.md, skill.yaml — extends outcomes for project planning

adapters/           Adapters (how services map to entities)
  reddit/          Maps Reddit API → post entity
  todoist/         Maps Todoist API → task entity
  whatsapp/        Maps WhatsApp DB → message, conversation, person entities

themes/            Visual styling (CSS)
```

**The flow:** 
1. Skills define entity types (schema, display, views)
2. Adapters declare which entities they provide (via `adapters:` section)
3. Entities with `show_as_app: true` appear on the desktop when adapters support them

---

## Writing Adapters

**For detailed adapter writing guidance, read the skill:**

```bash
~/.agentos/drive/skills/write-adapter.md
```

This covers:
- Entity reuse patterns (use existing entities before creating new ones)
- Entity-level utilities (e.g., `domain.dns_list` for DNS operations)
- Adapters and mappings
- Expression syntax (jaq)
- Testing requirements

### Quick Reference

**Adapter structure:**
```
adapters/{name}/
  readme.md     # YAML front matter + docs
  icon.svg      # Required
  tests/        # Functional tests
```

**Operations return types:** `entity`, `entity[]`, or `void`

**Entity-level utilities:** Name as `entity.utility_name` (e.g., `domain.dns_list`, not `dns_record.list`)

---

## Utility Return Types

Utilities are operations that don't fit standard CRUD patterns. Unlike operations (which return entities), utilities can return various shapes.

### When to Use Each Return Type

| Return Type | When to Use | Example |
|-------------|-------------|---------|
| `void` | Side-effect only, raw response | `logo_url` (returns image) |
| `operation_result` | Action success/fail | `remove_relation`, `dns_delete` |
| Model reference | Structured data shared across adapters | `dns_list` → `dns_record[]` |
| Inline schema | Adapter-specific introspection | `get_workflow_states` (Linear-only) |

### Standard Result Models

**`operation_result`** — Use for actions that succeed or fail:
```yaml
# Returns: { success: boolean, message?: string, id?: string }
utilities:
  remove_relation:
    returns: operation_result
    # ...
  
  add_blocker:
    returns: operation_result  # relation ID goes in `id` field
    # ...
```

**`batch_result`** — Use for bulk operations:
```yaml
# Returns: { succeeded: int, failed: int, total: int, errors?: string[] }
utilities:
  bulk_archive:
    returns: batch_result
    # ...
```

### Heuristics: Choosing the Right Return Type

**Use `operation_result` when:**
- The action succeeds or fails (previously you'd return `{ success: boolean }`)
- The caller only needs confirmation
- An ID of an affected/created resource is the only meaningful output

**Use a model reference when:**
- Multiple adapters return the same shape (e.g., `dns_record` across Gandi, Porkbun)
- The UI needs to render the result consistently
- AI agents need a predictable contract for downstream actions

**Use inline schema when:**
- The data is adapter-specific introspection (`get_workflow_states`, `get_cycles`)
- The shape is unlikely to be reused across adapters
- It's configuration/setup data, not domain data

**Use `void` when:**
- The response is raw (image, file, redirect)
- The action has no meaningful return data

### Examples

```yaml
# Good: Standard result for success/fail action
utilities:
  dns_delete:
    returns: operation_result

# Good: Model reference for shared concept
utilities:
  dns_list:
    returns: dns_record[]  # Defined in entities/common/

# Good: Inline for adapter-specific introspection
utilities:
  get_workflow_states:
    returns:
      id: string
      name: string
      type: string
    # Linear-specific, no need for shared model

# Good: Void for raw responses
utilities:
  logo_url:
    returns: void
    response:
      raw: true
```

---

## Writing Apps

**For detailed app writing guidance, read the skill:**

```bash
~/.agentos/drive/skills/write-app.md
```

### Quick Reference

**Entity structure:**
```
entities/{group}/
  {entity}.yaml   # Entity definition (one per file)
  icon.png        # Desktop icon (PNG preferred)
  views/          # TSX components + view configs
```

**Skill structure:**
```
skills/{skill}/
  skill.md        # Workflow guide (how to use entities)
  skill.yaml      # Metadata: extends, naming, relationships
  icon.png        # Optional
```

**Models can define:**
- `properties:` — Entity schema
- `operations:` — Standard CRUD (`[list, get, create, update, delete]`)
- `utilities:` — Entity-level helpers with custom return shapes
- `display:` — How to show in UI (`show_as_app: true` for desktop apps)

---

## Components

Entity components live in `entities/{group}/views/`. They compose framework primitives — never custom CSS.

**Key rules:**
- Use `data-*` attributes: `data-component="text" data-variant="title"`
- Proxy external images with `getProxiedSrc()`
- Export default: `export default MyComponent`

**See examples:** `entities/discussion/views/`, `entities/groups/views/`

---

## Testing

```bash
npm run validate              # Schema + test coverage (run first!)
npm test                      # Functional tests
npm test adapters/exa/tests    # Single adapter
```

**Validation checks:** Schema structure, test coverage, required files (icon).

**`.needs-work/`** — Adapters that fail validation are auto-moved here.

**Every operation needs at least one test.** Include `tool: "operation.name"` references even in skipped tests.

---

## Commands

```bash
npm run new-adapter <name>    # Create adapter scaffold
npm run validate             # Schema validation (run first!)
npm test                     # Functional tests
```

---

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.
