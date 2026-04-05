# Shapes

Shapes are typed record schemas that define the contract between skills and the engine. A shape declares what a record looks like: field names, types, relations to other records, and display rules.

Shapes live in `shapes/*.yaml` in source directories. The engine loads them at boot. Use `agentos test <skill>` to validate that your skill's output matches the declared shapes (see [Testing](testing.md)).

## Format

```yaml
product:
  also: [other_shape]       # "a product is also a ..." (optional)
  fields:
    price: string
    price_amount: number
    prime: boolean
  relations:
    contains: item[]         # array relation
    brand: organization      # single relation
  display:
    title: name
    subtitle: author
    image: image
    date: datePublished
    columns:
      - name: Name
      - price: Price
```

### `also` (tag implication)

Declares that this shape is also another shape. An email is also a message. A book is also a product. When the engine tags a record with `email`, it transitively applies `message` too. Both shapes' fields contribute to the record's type context.

`also` is transitive: if A is also B and B is also C, then A is also B and C.

### Field types

| Type | Stored as | Notes |
|------|-----------|-------|
| `string` | text | Short text |
| `text` | text | Long text, FTS eligible |
| `integer` | digits | Parsed from strings, floats truncated |
| `number` | decimal | Parsed from strings |
| `boolean` | true/false | Coerced from 1/0, "yes"/"no", "true"/"false" |
| `datetime` | ISO 8601 | Unix timestamps auto-converted, human dates parsed |
| `url` | text | Stored as-is, rendered as clickable link |
| `string[]` | JSON array | Each element coerced to string |
| `integer[]` | JSON array | Each element coerced to integer |
| `json` | JSON string | Opaque blob, no coercion |

### Standard fields

These are available on every record without declaring them in a shape:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | string | Record identifier |
| `name` | string | Primary label |
| `text` | text | Short summary |
| `url` | url | Canonical link |
| `image` | url | Thumbnail |
| `author` | string | Creator |
| `published` | datetime | Temporal anchor |
| `content` | text | Long body text (FTS, stored separately) |

### Relations

Relations declare connections to other records. Keys are edge labels, values are target shapes (`shape` or `shape[]` for arrays).

### Display

The `display` section tells renderers how to present this record:

- `title` — primary label field
- `subtitle` — secondary label
- `description` — preview text
- `image` — thumbnail
- `date` — temporal anchor for sort/display
- `columns` — ordered list for table views

---

## Design Principles

These principles guide shape design. Use the review checklist below after writing or editing a shape.

### 1. Entities over fields

If a field value is itself a thing with identity, it should be a **relation to another shape**, not a string field.

**Bad:** `shipping_address: string` (an address is a thing)
**Good:** `shipping_address: place` (a relation to a place record)

**Bad:** `email: string` on a person (an email is an account)
**Good:** `accounts: account[]` relation on person

Ask: *"Could this field value have its own page?"* If yes, it's a relation.

### 2. Separate identity from role

A person doesn't *have* a job title. A person *holds a role* at an organization for a period of time. The role is the relationship, not a field on the person.

**Bad:** `job_title: string` on person
**Good:** `role: role[]` relation where the role record carries title, organization, start_date, end_date

Same pattern applies to education, membership, authorship. If it has a time dimension or involves another entity, it's a role/relationship, not a field.

### 3. Currency always accompanies price

Any field representing a monetary amount needs a companion currency field. Never assume USD.

**Bad:** `price_amount: number` alone
**Good:** `price_amount: number` + `currency: string`

### 4. URLs that reference other things are relations

The standard `url` field is the record's own canonical link. But URLs that point to *other things* should be relations to the appropriate shape.

**Bad:** `website: url` on an organization (a website is its own entity)
**Good:** `website: website` relation

**Bad:** `external_url: url` on a post (the linked page is a thing)
**Good:** `links_to: webpage` relation

Ask: *"Is this URL the record itself, or does it point to something else?"*
- Record's own link: keep as `url` (standard field)
- Points to another thing: make it a relation

### 5. Keep shapes domain-agnostic

A shape should describe the *kind of thing*, not the *source it came from*. Flight details don't belong on an offer shape. Browser-specific fields don't belong on a webpage shape.

**Bad:** `total_duration: integer`, `flights: json`, `layovers: json` on offer (that's a flight, not an offer)
**Good:** offer has price + currency + offer_type. Flight is its own shape. Offer relates to flight.

### 6. Use `also` for genuine "is-a" relationships

`also` means tag implication: tagging a record with shape A also tags it with shape B. Use it when querying by B should include A.

**Good uses:**
- `email` also `message` (querying messages should include emails)
- `video` also `post` (querying posts should include videos)
- `book` also `product` (querying products should include books)
- `review` also `post` (querying posts should include reviews)

**Bad uses:**
- Don't use `also` just because shapes share some fields
- Don't create deep chains (A also B also C also D) — keep it shallow

### 7. Author is a shape, not just a string

The standard `author` field is a string for convenience. But when the author is a real entity with their own identity (a book author, a blog writer, a video creator), use a relation to the `author` or `account` shape.

**Quick attribution:** `author: "Paul Graham"` (standard string field)
**Rich attribution:** `written_by: author` or `posted_by: account` (relation)

Both can coexist — the string is for display, the relation is for traversal.

### 8. Address/Place is structured, not a string

Physical locations should be a `place` shape with structured fields (name, street, city, region, postal_code, country, coordinates). Inspired by Mapbox's geocoding model.

### 9. Playlists, shelves, and lists belong to accounts

Any collection (playlist, shelf, list, board) should have a `belongs_to: account` relation. Collections are owned.

### 10. Use ISO standards for standardized values

When a field represents something with an international standard, use the standard code:

- **Human languages** — ISO 639-1 codes (`en`, `es`, `ja`, `pt-BR`). Applies to transcript.language, webpage.language, content language fields. NOT programming languages (those use conventional names like `Python`, `Rust`).
- **Countries** — ISO 3166-1 alpha-2 codes (`US`, `GB`, `JP`). Use `country_code` field.
- **Currencies** — ISO 4217 codes (`USD`, `EUR`, `JPY`). Use `currency` field.
- **Timezones** — IANA timezone names (`America/New_York`, `Europe/London`).

Don't enforce via enum (too many values). Document the convention and let `agentos test` flag non-compliant values. See [Testing & Validation](testing.md) for how to run shape validation.

### 11. Separate content from context (NEPOMUK principle)

A video is a file. The social engagement around it is a post. A transcript is text. The meeting it came from is the context. Don't mix artifact properties with social properties on the same shape.

**Bad:** `video` has view_count, like_count, comment_count, posted_by (those are social context)
**Good:** `video` is a file with duration + resolution. A `post` contains the video and carries the engagement.

Ask: *"If I downloaded this to my hard drive, which fields would still make sense?"* Those are the artifact fields. Everything else is context that belongs on a wrapper entity.

### 12. Comments are nested posts, not a separate shape

A comment is a post that `replies_to` another post. A reply to a message is still a message. Don't create separate shapes for nested versions of the same thing — use the `replies_to` relation to express the hierarchy.

### 13. Booleans describe state, relations describe lineage

`is_fork: boolean` tells you nothing. `forked_from: repository` tells you the lineage. If a boolean implies a relationship to another entity, model the relationship instead.

**Bad:** `is_fork: boolean` (from what?)
**Good:** `forked_from: repository` (the source is traversable)

### 14. Booleans that encode direction are really relationships

`is_outgoing: boolean` on a message means "I sent this." But that information already lives in the `from: account` relation — if the `from` account is the user, it's outgoing. Don't duplicate relationship semantics as boolean flags.

**Bad:** `is_outgoing: boolean` on message
**Good:** `from: account` relation — direction is derived by comparing `from` to the current user

Same pattern: `is_sent`, `is_received`, `is_mine` — all derivable from a directional relation.

### 15. Booleans that encode cardinality are derivable

`is_group: boolean` on a conversation means "has more than two participants." That's not state — it's a count. Don't store what you can derive from the structure.

**Bad:** `is_group: boolean` on conversation
**Good:** `participant: account[]` relation — `is_group` is `len(participants) > 2`

Same pattern: `has_attachments` (derive from `attachment: file[]`), `has_unread` (derive from messages), `is_empty` (derive from children).

### 16. Source data doesn't dictate shape

A skill's source (API, database, scrape) returns whatever it returns. That doesn't constrain the shape. The Python function is the transformation boundary — it takes raw source data and returns shape-native dicts.

Apple Contacts gives flat strings: `Organization: Anthropic`, `Title: Engineer`. That doesn't mean person gets `organization: string`. It means the skill transforms those strings into a `roles: role[]` typed ref.

**Bad:** "The API returns `platform: string`, so the shape needs a `platform` field"
**Good:** "What kind of thing is this? Model it correctly. The skill transforms source data to fit."

Design shapes for the domain, not for the source. Every skill file is a template — other agents copy the patterns they see.

### 17. Model life like LinkedIn, not like a spreadsheet

People have roles at organizations. Roles have titles, departments, start dates, end dates. Education is a role at a school. Membership is a role in a community. Authorship is a role on a publication.

The LinkedIn mental model: a person has a timeline of positions, each connecting them to an organization with a title and time range. This is principle #2 made concrete.

```
person --roles--> role[] --organization--> organization
                         --title: "Engineer"
                         --department: "Research"
                         --start_date: 2024-01-15
                         --end_date: null (current)
```

This applies broadly: board membership, team membership, project assignment, course enrollment. If a relationship has a time dimension or a title, it's a role.

---

## Review Checklist

After writing or editing a shape, ask yourself:

- [ ] **Fields or relations?** For each string field, ask: *"Is this value itself an entity?"* If yes, make it a relation.
- [ ] **Currency with price?** Every monetary amount has a currency companion.
- [ ] **URLs audited?** Is each URL the record's own link, or does it point to another entity?
- [ ] **Domain-agnostic?** Would this shape make sense for a different source providing the same kind of thing?
- [ ] **`also` justified?** Does the `also` chain represent genuine "is-a" relationships that aid cross-type queries?
- [ ] **Author modeled correctly?** Is the author a string (quick attribution) or a relation (traversable entity)?
- [ ] **Addresses structured?** Are locations/addresses relations to place, not inline strings?
- [ ] **Collections owned?** Do lists/playlists/shelves have a `belongs_to` relation?
- [ ] **Roles, not fields?** Are time-bounded relationships (jobs, education, membership) modeled as role relations, not person fields?
- [ ] **Display makes sense?** Are the right fields in title/subtitle/columns for this shape?
- [ ] **Content vs context?** If this is a media artifact, are social metrics on a wrapper post instead?
- [ ] **Nesting via reply_to?** Is a "sub-type" really just this shape with a parent relation?
- [ ] **ISO standards?** Are languages (ISO 639-1), countries (ISO 3166-1), currencies (ISO 4217) using standard codes?
- [ ] **Booleans or relations?** Does any boolean imply a relationship? (`is_fork` → `forked_from`)
- [ ] **Direction booleans?** Is `is_outgoing`/`is_sent` derivable from a `from` relation?
- [ ] **Cardinality booleans?** Is `is_group`/`has_attachments` derivable from counting a relation?
- [ ] **Source-independent?** Did you design for the domain, or did the API shape leak into the schema?
- [ ] **Roles modeled as LinkedIn?** Are jobs/education/memberships `role[]` relations with title + org + time range?

---

## Returning shape-native data from operations

When an operation declares `returns: email[]`, the Python function returns dicts whose keys match the shape. The shape is the contract — no separate mapping layer sits between the Python code and the engine.

```yaml
# shapes/email.yaml
email:
  also: [message]
  fields:
    from_email: string
    to: string[]
    cc: string[]
    labels: string[]
    thread_id: string
  relations:
    from: account
    conversation: conversation
  display:
    title: name
    subtitle: from_email
    date: datePublished
```

```yaml
# skill.yaml
operations:
  get_email:
    returns: email         # points to the email shape
    python:
      module: ./gmail.py
      function: get_email
```

```python
# gmail.py — returns email-shaped dicts directly
def get_email(id: str, _call=None) -> dict:
    return {
        "id": msg_id,
        "name": subject,              # standard field
        "text": snippet,              # standard field
        "url": web_url,               # standard field
        "published": date,             # standard field
        "content": body_text,          # standard field (FTS)
        "from_email": sender,          # shape-specific field
        "to": recipients,             # shape-specific field
        "labels": label_ids,          # shape-specific field
    }
```

The Python code does the field mapping — it transforms raw API responses into shape-native dicts. Standard fields (`id`, `name`, `text`, `url`, `image`, `author`, `published`, `content`) are available on every shape without declaring them.

### Canonical fields

The renderer resolves entity display from standard fields. Every Python return should populate as many of these as the source data supports — they drive consistent previews, detail views, and search results across all skills.

| Field           | Purpose                                          |
|-----------------|--------------------------------------------------|
| `name`          | Primary label / title                            |
| `text`          | Short summary or snippet for preview rows        |
| `url`           | Clickable link                                   |
| `image`         | Thumbnail / hero image                           |
| `author`        | Creator / brand / owner                          |
| `published` | Temporal anchor                                  |
| `content`       | Long body text (stored separately, FTS-indexed)  |

Not every entity has all of these — a product may have no `published`, an order may have no `image`. Map what the source provides; skip what doesn't apply.

### Typed references (entity relationships)

To create linked entities and graph edges, return nested dicts keyed by entity type:

```python
def get_email(id: str, _call=None) -> dict:
    return {
        "id": msg_id,
        "name": subject,
        # Single typed ref — creates: email --from--> account
        "from": {
            "account": {
                "handle": sender_email,
                "platform": "email",
                "display_name": sender_name,
            }
        },
        # Array typed ref — creates: email --to--> account (one per recipient)
        "to": {
            "account[]": [
                {"handle": addr, "platform": "email", "display_name": name}
                for addr, name in recipients
            ]
        },
    }
```

The outer key (`from`, `to`) becomes the edge label. The inner key (`account`, `account[]`) is the entity tag. The engine auto-creates/deduplicates the linked entity and adds the edge.

A typed ref is collapsed to null if none of its identity fields (`id` or `name`) survive — so partial data doesn't create ghost entities.

---

## Validation

Shape conformance is checked at two levels:

### Pre-commit (static)

`bin/audit-skills.py` parses Python return dict literals via AST and warns if keys don't match the declared shape. Runs automatically on every commit. Catches dict-literal returns but misses dynamic construction, helper functions, and `_call` composition.

### Runtime

The engine validates every entity-returning skill call after execution. If the returned data contains keys not declared in the shape (fields, relations, or standard fields), a warning is logged to `engine.log`. Missing identity fields (`id` and `name`) also trigger warnings.

Runtime validation catches everything the static check misses — it sees the actual data. Check `~/.agentos/logs/engine.log` for `Shape conformance` warnings after running a skill.

Both checks are advisory (warnings, not errors). They exist to surface non-conformant skills, not to block execution.

---

## Prior Research

Extensive entity modeling research lives in `/Users/joe/dev/entity-experiments/`. These are not authoritative — many are outdated — but contain valuable principles and platform analysis worth consulting when designing new shapes.

### Entity & Ontology Research
- `schema-entities.md` — Core entity type definitions, OGP foundation, Joe's hypotheses on note vs article
- `schema-relationships.md` — Relationship type catalog and design patterns
- `research/entities/open-graph-protocol.md` — OGP types, why flat beats hierarchical
- `research/entities/google-structured-data.md` — Schema.org structured data patterns

### Platform Research
- `research/platforms/google-takeout.md` — 72 Google products analyzed for entity types (Contacts, Calendar, Drive, Gmail, Photos, YouTube, Maps, Chrome, Pay, Play)
- `research/platforms/facebook-graph.md` — Facebook Graph API entity model
- `research/platforms/familysearch.md` — GEDCOM X genealogical data model (two relationship types + qualifiers, computed derivations, source citations)

### Relationship Research
- `research/relationships/genealogical-relationships.md` — Family relationship modeling patterns
- `research/relationships/relationship-modeling.md` — General relationship design
- `research/relationships/schema-org-relationships.md` — Schema.org relationship types
- `research/relationships/ogp-relationships.md` — OGP relationship patterns
- `research/relationships/no-orphans-constraint.md` — Why every entity needs at least one connection

### Systems Research
- `research/systems/outcome-entity.md` — Outcome/goal entity modeling
- `research/context/pkm-community.md` — Personal knowledge management patterns
- `research/context/semantic-file-systems.md` — NEPOMUK and semantic desktop research
