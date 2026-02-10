# Contributing to the AgentOS Community

Declarative YAML for entities, adapters, apps, skills, and themes.

**Schema reference:** `tests/adapters/adapter.schema.json` — the source of truth for adapter structure.

**Using an AI agent?** Have it read `AGENTS.md` for operational guidance and workflow patterns.

---

## Development Workflow

**Edit directly in this repo.** The server's `sources` setting points here (`~/dev/agentos-community`). Changes take effect on server restart.

```bash
# 1. Edit directly in the community repo (this is the live source)
vim ~/dev/agentos-community/adapters/reddit/readme.md

# 2. Restart AgentOS server and test
cd ~/dev/agentos && ./restart.sh
curl -X POST http://localhost:3456/api/adapters/reddit/post.list \
  -d '{"subreddit": "programming", "limit": 1}'

# 3. Validate and commit
cd ~/dev/agentos-community
npm run validate
git add -A && git commit -m "Update Reddit adapter"
```

---

## Manifest Auto-Generates

**Never edit `manifest.json` manually!** 

GitHub Actions automatically scans the repo on push to `main`, reads YAML front matter, and generates an updated manifest.

```bash
# Test locally
node scripts/generate-manifest.js        # Regenerate
node scripts/generate-manifest.js --check # Validate only
```

---

## Architecture Overview

**Full taxonomy:** See [agentos/ARCHITECTURE.md](https://github.com/jcontini/agentos/blob/main/ARCHITECTURE.md) for entities, skills, adapters, vibes, client vs interface.

**Entity YAML files are the single source of truth for entity types.** Want a new entity type? Add a YAML file in `entities/`. The entity defines:

- **Schema** — properties, types, validation
- **Relationships** — what this entity connects to (via references or relationship types)
- **Display** — how it appears in generic components (primary field, image, icon, sort)

Adapters map external APIs to these entity types. Apps provide visual experiences on the desktop. Both are separate from the entity definitions.

```
entities/          Entity type definitions (single source of truth)
  _primitives/     Abstract base types (document, media, collection, etc.)
  _relationships/  Relationship types (contains, references, posts, etc.)
  _system/         operations.yaml (standard operation definitions)
  task.yaml        All entities are flat YAML files
  person.yaml
  video.yaml
  ...

adapters/          Adapters (how services map to entities)
  reddit/          Maps Reddit API → post entity
  todoist/         Maps Todoist API → task entity
  youtube/         Maps YouTube API → video, community, account entities
  ...

skills/            Workflow guides (AI context, not visual)
  write-adapter/   How to build an adapter

themes/            Visual styling (CSS)
```

**The flow:** 
1. Entity YAMLs define data types (schema + display hints)
2. Adapters declare which entities they provide and how to map API data
3. The Browser app renders any entity type using generic components that read display hints
4. Custom apps (when needed) provide specialized views on top of entities

---

## Writing Adapters

**For detailed adapter writing guidance, read the skill:**

```bash
skills/write-adapter.md
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

## Entity Schemas

**Entities are pure data model.** They define what things ARE — properties, types, display hints. No views, no visual logic.

```yaml
# entities/video.yaml
id: video
plural: videos
extends: media
name: Video
description: Video content with metadata and optional transcript

properties:
  remote_id: { type: string }
  transcript: { type: string }
  view_count: { type: integer }

operations: [get, search, list, transcript]

display:
  primary: title
  secondary: posted_by.display_name
  description: description
  image: thumbnail
  icon: play
  sort:
    - field: published_at
      order: desc
```

The `display` section tells generic components how to render this entity. No custom code needed — `entity-list` reads `display.primary` for the title, `display.image` for the thumbnail, etc.

### Entity Model Extension Mechanisms

**`extends:`** — Type hierarchy. Entities inherit properties from a parent type. The Rust resolver handles multi-level inheritance (e.g., `document → post`, `media → video`).

```yaml
# post.yaml — inherits id, content, author, title, url, published_at from document
id: post
extends: document
properties:
  community:
    references: community
```

**`vocabulary:`** — Context-appropriate naming. Rename inherited properties for domain context. The graph still treats them as equivalent.

```yaml
id: my-entity
extends: parent
vocabulary:
  url: source_url
```

**`data: {}`** — Adapter-specific extensions. An open object property for adapter-specific fields that don't belong in the shared schema.

```yaml
# In adapter mapping — store adapter-specific fields
mapping:
  data.priority_label: .priority_label
  data.section_id: .section_id
```

**System properties:** Every entity automatically gets `created_at` and `updated_at` (datetime). These don't need to be declared in YAML — the resolver adds them.

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
