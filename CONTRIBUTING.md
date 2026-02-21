# Contributing to the AgentOS Community

Everything lives here — entities, skills, apps, and themes. Core is a generic engine; this repo is the ecosystem.

**Three concerns:** Entities define the Memex model (`entities/`). Skills connect to services and provide agent context (`skills/`). Apps are optional UI experiences (`apps/`).

**Schema reference:** `tests/skills/skill.schema.json` — the source of truth for skill structure.

**Using an AI agent?** Have it read `AGENTS.md` for operational guidance and workflow patterns.

---

## Development Workflow

**Edit directly in this repo.** The server's `sources` setting points here (`~/dev/agentos-community`). Changes take effect on server restart.

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

**Full taxonomy:** See [agentos/ARCHITECTURE.md](https://github.com/jcontini/agentos/blob/main/ARCHITECTURE.md) for entities, skills, transformers, vibes, client vs interface.

**Entity YAML files are the single source of truth for entity types.** Want a new entity type? Add a YAML file in `entities/`. The entity defines:

- **Schema** — properties, types, validation
- **Relationships** — what this entity connects to (via references or relationship types)
- **Display** — how it appears in generic components (primary field, image, icon, sort)

Skills map external APIs to these entity types. Apps provide optional visual experiences on the desktop. Both are separate from the entity definitions.

```
entities/          Entity type definitions (single source of truth)
  _primitives/     Abstract base types (document, media, collection, etc.)
  _relationships/  Relationship types (contains, references, posts, etc.)
  _system/         operations.yaml (standard operation definitions)
  task.yaml        All entities are flat YAML files
  person.yaml
  video.yaml
  ...

skills/            Skills — service connections + agent context
  reddit/          Maps Reddit API → post entity
  todoist/         Maps Todoist API → task entity
  youtube/         Maps YouTube API → video, community, account entities
  write-skill.md   Workflow guide (AI context, no API binding)
  shell-history.md Agent instructions (no API binding)

apps/              Visual apps (UI experiences)
  videos/          Video player with channel info and embed
  browser/         Universal entity viewer (migrating from core)
  settings/        System preferences (migrating from core)
  ...

themes/            Visual styling (CSS)
```

**The flow:** 
1. Entity YAMLs define data types (schema + display hints)
2. Transformers declare which entities they provide and how to map API data
3. The Browser app renders any entity type using generic components that read display hints
4. Custom apps (when needed) provide specialized views on top of entities

---

## Entity Design Principles

These principles govern how we model data in the Memex. They're not preferences — they're architectural decisions that compound. Getting them wrong creates tech debt that infects every feature built on top.

### Computed, Not Stored

**Properties that can be derived from the graph are never stored as fields.** They're computed at query time or inferred by traversal.

```yaml
# Good: status is computed from graph state
computed:
  status: |
    if .completed then "done"
    elif (.blockers | length > 0) then "blocked"
    else "ready"
    end

# Bad: storing a derived property as a field
properties:
  status: { type: string, enum: [done, blocked, ready] }  # ← this is just a cache of graph state
```

Real examples in the codebase:
- **Task status**: computed from completion + blockers
- **Narrative positions**: inferred from the enables graph via a goal
- **Contact cards**: views computed from graph traversals over a person's claimed accounts
- **Place membership**: computed by netting add/remove relationships
- **Reply counts**: computed by traversal

**Corollary: Don't create entities for things that are just views over other entities.** The "stage" of a relationship between two people isn't an entity or a stored property. It's what the graph tells you when you look at the events, conversations, emotions, and engagement between them. A first date is a date entity. "We met on Hinge" is an event. Milestones are events. The graph stores atoms; intelligence computes molecules.

### Everything on the Graph

**No shadow tables, no side stores.** If something is worth tracking — provenance, observations, audit trails, agent memory — it's an entity with relationships. The 10 MCP tools work for everything because everything is an entity. If you find yourself designing a separate SQL table or JSON file for structured data, stop and model it as entities instead.

### Entities Are Things, Not Relationships

**If two entities have a connection, that's a relationship — not a new entity type.** Don't create a "Friendship" entity to link two people. The friendship IS the subgraph: the events, conversations, shared experiences, and edges between them. The relationship edges (`engage`, `reference`, etc.) capture the connection. Intelligence synthesizes the narrative.

Relationships already have properties (`data` field), temporal bounds (`started_at`, `ended_at`), and provenance (`skill`, `account`). If you need richer connection data, add properties to the relationship — don't promote it to an entity.

---

## Attribution Model — Accounts, Not People

**CRITICAL:** When pulling content from social platforms (YouTube, Reddit, Twitter, HackerNews, etc.), create **account entities**, not person entities.

### The Model

```
Account (platform identity) → on_platform → Product (YouTube, Reddit, Phone, Email)
Person (the human) → claims → Account (with epistemic provenance)
```

**Why this matters:**
1. **You don't know it's a person** — @3blue1brown could be one person, a team, or a brand account
2. **Navigation is the point** — Click a username in a comment → jump to that account → see all their posts across platforms → discover it's the same person you follow elsewhere
3. **The Memex enables discovery** — "Oh, patio11 on HackerNews is the same person as patio11 on Twitter? Worth following."
4. **Governance is via accounts** — An account owns a channel, not a person directly. Brand accounts can have multiple person-owners.

### When to Use Person vs Account

| Use Account | Use Person |
|-------------|-----------|
| Social media posts (Reddit, Twitter, YouTube) | Contact from Apple Contacts |
| Comments and replies | Author from Hardcover book API |
| Channel ownership | Meeting participant |
| Anonymous commenters | Family member in iMessage |

**The difference:** If the source is a public platform where identity is mediated by the platform, it's an account. If it's a direct personal identifier (your contacts, your calendar), it's a person.

### Example: HackerNews Posts

```yaml
# CORRECT — creates account entities
posted_by:
  account:
    id: .author
    platform: '"hackernews"'
    handle: .author
    display_name: .author
    url: '"https://news.ycombinator.com/user?id=" + .author'
```

```yaml
# WRONG — creates person entities
posted_by:
  person:
    id: .author
    name: .author
```

**Why wrong:** You don't know if "patio11" is Patrick McKenzie (person) just from the HackerNews API. You know there's an account called "patio11" on HackerNews. Later, via `claims` relationships with provenance, you might link that account to a person entity.

### Platform as Product Reference

The `platform` field on account should reference a product entity:

```yaml
# Account entity
platform:
  references: product  # ← Product entity (YouTube, Reddit, Phone, Email)
```

This enables:
- Product timeline ("Show me when Twitter became X")
- Ownership tracking (WhatsApp → made_by → WhatsApp Inc → acquired_by → Meta)
- Platform availability ("Does this account still exist?" depends on product.status)

**See:** `.ROADMAP/.archived/account-entity.md` for complete account/person/product architecture.

---

## Writing Skills

**For detailed skill writing guidance, read the skill:**

```bash
skills/write-skill.md
```

This covers:
- Entity reuse patterns (use existing entities before creating new ones)
- Entity-level utilities (e.g., `domain.dns_list` for DNS operations)
- Transformers and mappings
- Expression syntax (jaq)
- Testing requirements

### Quick Reference

**Skill structure:**
```
skills/{name}/
  readme.md     # YAML front matter + docs
  icon.svg      # Required
  tests/        # Functional tests
```

**Operations return types:** `entity`, `entity[]`, or `void`

**Entity-level utilities:** Name as `entity.utility_name` (e.g., `domain.dns_list`, not `dns_record.list`)

### Mapping Field Types

Transformer mappings support three field types, detected by structure:

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

**Body content** — Routes rich content to the `entity_bodies` table (indexed by FTS5):
```yaml
mapping:
  _body: .content                # → stored in entity_bodies, indexed by FTS5
  _body_role: '"transcript"'     # → optional role key (default: "body")
```

The extraction pipeline detects `_body`, strips it from entity data, and stores it in the `entity_bodies` table with SHA256 hashing and MIME type tracking. Content is automatically indexed by FTS5 for full-text search with BM25 ranking and highlighted excerpts.

Use `_body` when content is too large for the JSON `data` column (transcripts, articles, full page text) or when you want body-specific search excerpts. Short text (descriptions, snippets) can stay in `data` — it's already FTS5-searchable via the data column.

**Strategy for existing fields:** For content-first entities (webpages, documents), replace the `content` field with `_body`. For metadata entities with meaningful descriptions (tasks, issues), map both — keep `description` in data for display and add `_body` for enhanced search:

```yaml
mapping:
  description: .description    # stays in entity data for list views
  _body: .description          # also stored as body for FTS5 search
```

**Multiple body roles:** An entity can have multiple bodies keyed by role (`body`, `summary`, `transcript`, `excerpt`). Use `_body_role` to specify. Currently the extraction pipeline supports one `_body` per mapping; additional roles can be added via the body API directly.

**Response flattening:** Typed reference data is automatically flattened in API responses for view consumption. The nested `{ entity_type: { fields }, _rel: { ... } }` structure becomes `{ _type: entity_type, ...fields }`. Views can then use dot notation: `{{posted_by.display_name}}`, `{{posted_in.name}}`.

**Content attribution pattern:** Social content should use the `posts` relationship (`account --posts--> content`) rather than `creator: references: person`. An account posting content is what we can observe; the person behind the account is a separate inference via the `claims` relationship. See `entities/_relationships/posts.yaml` for details.

---

## Utility Return Types

Utilities are operations that don't fit standard CRUD patterns. Unlike operations (which return entities), utilities can return various shapes.

| Return Type | When to Use | Example |
|-------------|-------------|---------|
| `void` | Side-effect only, or action confirmation | `delete`, `archive`, `add_blocker` |
| Model reference | Structured data shared across skills | `dns_list` → `dns_record[]` |
| Inline schema | Skill-specific introspection | `get_workflow_states` (Linear-only) |

**Use a model reference when:**
- Multiple skills return the same shape (e.g., `dns_record` across Gandi, Porkbun)
- The UI needs to render the result consistently
- AI agents need a predictable contract for downstream actions

**Use inline schema when:**
- The data is skill-specific introspection (`get_workflow_states`, `get_cycles`)
- The shape is unlikely to be reused across skills
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

# Good: Inline for skill-specific introspection
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

**`data: {}`** — Skill-specific extensions. An open object property for skill-specific fields that don't belong in the shared schema.

```yaml
# In transformer mapping — store skill-specific fields
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
npm test skills/exa/tests     # Single skill
```

**Validation checks:** Schema structure, test coverage, required files (icon).

**`.needs-work/`** — Skills that fail validation live here until fixed.

**Every operation needs at least one test.** Include `tool: "operation.name"` references even in skipped tests.

---

## Commands

```bash
npm run new-skill <name>     # Create skill scaffold
npm run validate             # Schema validation (run first!)
npm test                     # Functional tests
```

---

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.
