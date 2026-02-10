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
  _primitives/     Abstract base types (document, collection, etc.)
  _relationships/  Relationship types (contains, enables, etc.)
  _system/         operations.yaml (standard operation definitions)
  post/            post.yaml + views/  (entities with views keep a folder)
  community/       community.yaml + views/
  task.yaml        Flat entity files (no views, no subfolder)
  person.yaml
  ...

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

### Mapping Field Types

Adapter mappings support three field types, detected by structure:

**String** — Simple jaq expression (stored as entity property):
```yaml
mapping:
  title: .content
  url: .webpage_url
  published_at: .upload_date
```

**Relationship ref** — Links to an existing entity by service_id:
```yaml
mapping:
  project_id:
    ref: journey          # entity type to look up
    value: .project_id    # jaq expression for the service_id (scalar or array)
    rel: includes         # optional: inferred from schemas if unambiguous
```

**Typed reference** — Creates a new linked entity + relationship:
```yaml
mapping:
  # Creates an account entity + posts relationship (account → content)
  posted_by:
    account:
      id: .channel_id
      platform: '"youtube"'
      handle: .channel
      display_name: .channel
      platform_id: .channel_id
      url: .channel_url
    _rel:
      type: '"posts"'
      reverse: true

  # Creates a document entity + references relationship with role
  transcript_doc:
    document:
      id: '(.id) + "_transcript"'
      title: '"Transcript: " + .title'
      content: .transcript
      url: .webpage_url
    _rel:
      type: '"references"'
      role: '"transcript_of"'
      reverse: true
```

Typed references support **all entity fields**, not just identity. The entity schema's `identifiers` list determines which fields are used for deduplication — all other fields are stored as entity properties.

The optional `_rel` block:
- `type` — overrides the relationship type (default: the mapping field name)
- `reverse` — if `true`, flips the relationship direction so the linked entity is the `from` side (e.g., `account --posts--> video` instead of `video --posts--> account`)
- Any other key — stored as relationship data (e.g., `role` for `references` relationships)
- All `_rel` values are jaq expressions (use `'"literal"'` for string constants)

**Response flattening:** Typed reference data is automatically flattened in API responses for view consumption. The nested `{ entity_type: { fields }, _rel: { ... } }` structure becomes `{ _type: entity_type, ...fields }`. Views can then use dot notation: `{{posted_by.display_name}}`, `{{posted_in.name}}`.

**Content attribution pattern:** Social content should use the `posts` relationship (`account --posts--> content`) rather than `creator: references: person`. An account posting content is what we can observe; the person behind the account is a separate inference via the `claims` relationship. See `entities/_relationships/posts.yaml` for details.

---

## Utility Return Types

Utilities are operations that don't fit standard CRUD patterns. Unlike operations (which return entities), utilities can return various shapes.

| Return Type | When to Use | Example |
|-------------|-------------|---------|
| `void` | Side-effect only, or action confirmation | `delete`, `archive`, `add_blocker` |
| Model reference | Structured data shared across adapters | `dns_list` → `dns_record[]` |
| Inline schema | Adapter-specific introspection | `get_workflow_states` (Linear-only) |

**Use a model reference when:**
- Multiple adapters return the same shape (e.g., `dns_record` across Gandi, Porkbun)
- The UI needs to render the result consistently
- AI agents need a predictable contract for downstream actions

**Use inline schema when:**
- The data is adapter-specific introspection (`get_workflow_states`, `get_cycles`)
- The shape is unlikely to be reused across adapters
- It's configuration/setup data, not domain data

**Use `void` when:**
- The action is a side-effect (delete, archive, add relationship)
- The response is raw (image, file, redirect)
- The caller only needs confirmation that it worked

### Examples

```yaml
# Good: Void for side-effect actions
utilities:
  dns_delete:
    returns: void

# Good: Model reference for shared concept
utilities:
  dns_list:
    returns: dns_record[]  # Defined in entities/dns_record.yaml

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

**Entity structure (flat):**
```
entities/
  {entity}.yaml         # Most entities are flat files at root
  {entity}/             # Entities with views get a folder
    {entity}.yaml
    views/              # TSX components + view configs
  _primitives/          # Abstract base types
  _relationships/       # Relationship types
  _system/operations.yaml # Standard operation definitions
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

## Entity Model Extension Mechanisms

The entity model supports three extension mechanisms. Together they allow community contributors to build rich type hierarchies while keeping individual schemas clean.

### `extends:` — Type Hierarchy

Entities can inherit properties from a parent type. The Rust resolver handles multi-level inheritance (e.g., `document → post`, `media → video`). Child entities get all parent properties plus their own.

```yaml
# post.yaml — inherits id, content, author, title, url, published_at from document
id: post
extends: document
properties:
  community:
    references: community
  # ... post-specific properties
```

### `vocabulary:` — Context-Appropriate Naming

When inheriting a property, you can rename it for domain context. The graph still treats them as equivalent — querying by the renamed field works transparently.

```yaml
# Example: if an entity inherits `url` but wants it called `source_url`
id: my-entity
extends: parent
vocabulary:
  url: source_url
properties:
  # No explicit `source_url` needed — vocabulary override handles it
  some_field:
    type: string
```

Both the Rust resolver and JS validator resolve vocabulary overrides. Inherited identifiers are also renamed.

### `data: {}` — Adapter-Specific Extensions

An open object property for adapter-specific data that doesn't belong in the shared schema. Adapters can store extra fields here without modifying the entity definition.

```yaml
# In entity YAML
data:
  type: object
  description: Domain-specific extensions

# In adapter mapping — store adapter-specific fields
adapters:
  task:
    mapping:
      data.priority_label: .priority_label
      data.section_id: .section_id
```

### System Properties

Every entity automatically gets `created_at` and `updated_at` (datetime) as system-injected properties. These don't need to be declared in YAML — the resolver adds them. Adapters can map source timestamps into them.

---

## Components

Entity components live in `entities/{entity}/views/`. They compose framework primitives — never custom CSS.

**Key rules:**
- Use `data-*` attributes: `data-component="text" data-variant="title"`
- Proxy external images with `getProxiedSrc()`
- Export default: `export default MyComponent`

**See examples:** `entities/post/views/`, `entities/community/views/`

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
