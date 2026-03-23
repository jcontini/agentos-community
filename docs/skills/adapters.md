# Adapters

Adapters map raw API responses into AgentOS entities. Define the shape once in `adapters:` and let operations reference it via `returns:`.

## Canonical fields

The renderer (`render.rs`) and markdown previews resolve entity display from a fixed set of **canonical fields**. Every adapter should map as many of these as the source data supports — they are the reason entities look consistent across skills in previews, detail views, and search results.

| Field           | Purpose                                          | Renderer fallback chain                                    |
|-----------------|--------------------------------------------------|------------------------------------------------------------|
| `name`          | Primary label / title                            | `name` → `title` → `conversation_name`                    |
| `text`          | Short summary or snippet for preview rows        | `text` → `description` → `content` → `snippet`            |
| `url`           | Clickable link                                   | —                                                          |
| `image`         | Thumbnail / hero image                           | —                                                          |
| `author`        | Creator / brand / owner                          | —                                                          |
| `datePublished` | Temporal anchor (accepts several date aliases)   | `datePublished` → `date` → `created_at` (see `render.rs`) |

Not every entity has all six — a product may have no `datePublished`, an order may have no `image`. Map what the source provides; skip what doesn't apply.

### Comment convention

Mark the boundary between canonical and skill-specific fields with comments so the two sections are visually obvious:

```yaml
adapters:
  result:
    # --- Canonical fields (rendered in previews / markdown) ---
    id: .url
    name: .title
    text: '.text // .summary'
    url: .url
    image: .image
    author: .author
    datePublished: .publishedDate
    # --- Skill-specific data ---
    data.score: .score
```

For lightweight relationship entities you can use the shorter `# --- Canonical fields ---` header. The `data.*` section comment is optional when there are only one or two extra fields, but always include the canonical header.

### Merge rules and deduplication

**Source of truth in core:** `crates/core/src/view/render.rs` — `project_item` (preview) and `canonicalize_full_item` (full/detail JSON) define how raw entity keys map into the stable shape. The fallback chains in the table above are applied at render time, so mapping to the *first* key in the chain is preferred (e.g. `name` over `title`).

**Import / remember / FTS:** `crates/core/src/execution/extraction.rs` — `prepare_node_data` treats **`content`** (and optional **`content_role`**) specially: that string is stored in the **`content` table** (indexed into the FTS **`body`** column). Other scalar fields (including `text`, `description`, `url`, …) become **node vals** and are folded into the FTS **`vals`** column on rebuild. Long or searchable bodies should use **`content`**, not a second copy in `text`/`description`.

Map each source field to one canonical key. The audit script flags duplicate jaq expressions across sibling keys — if you see the advisory, pick one key and use `data.*` for any secondary exposure.

## Typed references (entity relationships)

Typed references create **linked entities** and **graph edges** from a single adapter definition. The outer key becomes the edge label; the inner key is the entity tag. The engine auto-creates/deduplicates the linked entity and adds the edge.

### Single typed ref

```yaml
adapters:
  email:
    id: .id
    name: .subject
    # Creates: email --from--> account entity
    from:
      account:
        handle: '.from_email'
        platform: '"email"'
        display_name: '.from_name'
```

The `from:` field name becomes the edge label. `account:` is the entity tag — the linked entity is tagged `account` and deduped by its `id` (or first string field if no `id`). Each field inside (`handle`, `platform`, `display_name`) is a jaq expression evaluated against the raw API response.

### Array typed ref (`[]` + `_source`)

When a field can produce multiple linked entities, use the array syntax:

```yaml
    # Creates: email --to--> account (one edge per recipient)
    to:
      account[]:
        _source: '.recipients | map({email: .address, name: .display_name})'
        handle: .email
        platform: '"email"'
        display_name: .name
```

`account[]` signals the engine to expect an array. `_source` is a jaq expression evaluated against the raw response that produces an array of objects; each inner field is then evaluated per-element.

### Deduplication

Linked entities are deduped by `(skill_id, account, remote_id)` where `remote_id` comes from the `id` field in the typed ref (or the first string field as fallback). This means:

- Two emails from `clerk.dev` produce **one** domain entity — the second is an upsert
- Edges are created regardless — both emails link to the same domain node
- Vals on the linked entity are updated on each upsert (last-write-wins)

### Edge direction

Edges always point **from the parent entity to the linked entity**:

```
email --from--> account
email --domain--> domain
order --contains--> product
```

The field name is the edge label. Choose names that read naturally as a relationship.

### Real-world example: domain extraction

The Gmail skill extracts sender domains from email addresses:

```yaml
adapters:
  email:
    # Sender domain (single)
    domain:
      domain:
        id: '...jaq to extract domain from From header...'
        name: '...same expression...'

    # Recipient domains (array — multiple To addresses)
    to_domain:
      domain[]:
        _source: '...jaq that produces [{id: "gmail.com", name: "gmail.com"}, ...]...'
        id: .id
        name: .name
```

This produces `email --domain--> domain` and `email --to_domain--> domain` edges, with domain entities automatically deduplicated by domain string.

### How it works under the hood

1. **Mapping** (`mapping.rs`): jaq expressions are evaluated against the raw API response, producing nested JSON like `{ "domain": { "domain": { "id": "exa.ai", "name": "exa.ai" } } }`
2. **Extraction** (`extraction.rs`): `process_typed_references` reads the adapter mapping, detects typed refs via `parse_typed_reference`, finds the evaluated data in the mapped response, and calls `extract_linked_node_from_values` to create/upsert the linked entity
3. **Edge creation**: `create_edge_on` links the parent entity to the linked entity using the field name as the edge label

The extraction step loads the skill definition **fresh from disk** (via `load_skill_by_id`), so changes to `skill.yaml` take effect immediately on the next `run()` call — no engine restart needed.

## Rules

- Put canonical fields directly in the adapter body
- Keep default mapping in `adapters.<entity>`
- Use `data.*` for adapter-specific extra fields
- Use `content` only for long body text that should be stored separately (do not also mirror the same long text into `text` unless you mean to)
- Map to an existing entity type whenever possible

Example:

```yaml
adapters:
  result:
    # --- Canonical fields (rendered in previews / markdown) ---
    id: .url
    name: .title
    text: '.text // .summary'
    url: .url
    image: .image
    author: .author
    datePublished: .publishedDate
    # --- Skill-specific data ---
    data.score: .score
```
