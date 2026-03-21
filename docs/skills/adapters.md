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

## Adapter relationships

Adapters can declare relationships between entities. A nested block under a canonical field creates a graph edge from the adapted entity to the related entity:

```yaml
adapters:
  account:
    # --- Canonical fields (rendered in previews / markdown) ---
    id: .id
    name: .title
    # --- Skill-specific data ---
    data.category: .category

    in_vault:
      vault:
        # --- Canonical fields ---
        id: .vault.id
        name: .vault.name
```

This creates an `in_vault` edge from each `account` entity to its parent `vault` entity. The nested adapter (`vault:`) follows the same mapping rules — `id`, `name`, and `data.*` fields. The engine creates or finds the related entity and adds the edge.

Use relationships when entities have a natural containment or ownership structure (items in vaults, messages in conversations, tasks in projects). The relationship name (`in_vault`) becomes the edge label on the graph.

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
