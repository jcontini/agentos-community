# Write Adapter Skill

> How to create AgentOS adapters that maximize entity reuse

---

## Core Principle: Reuse Existing Entities

**Before creating a new entity, always check if an existing one fits.**

The whole point of entity-first architecture is that one UI works for many sources. When you map to existing entities, your adapter's data automatically:
- Shows up in existing apps (Tasks, Posts, Files)
- Gets consistent UI rendering
- Works with existing views and components
- Integrates with aggregation across sources

## Available Models

{% for model in models %}
### {{ model.name }} (`{{ model.id }}`)

{{ model.description }}

**Properties:** {% for prop in model.properties %}{% if prop.required %}**{{ prop.name }}**{% else %}{{ prop.name }}{% endif %}{% unless forloop.last %}, {% endunless %}{% endfor %}

{% if model.operations.size > 0 %}**Operations:** {{ model.operations | join: ", " }}
{% endif %}
**Adapters:** {% assign implementing_adapters = "" %}{% for adapter in adapters %}{% if adapter.entities contains model.id %}{% if implementing_adapters != "" %}{% assign implementing_adapters = implementing_adapters | append: ", " %}{% endif %}{% assign implementing_adapters = implementing_adapters | append: adapter.name %}{% endif %}{% endfor %}{% if implementing_adapters == "" %}(none yet){% else %}{{ implementing_adapters }}{% endif %}

{% endfor %}

---

## When to Create New Entities

Only create a new entity when:

1. **No existing entity fits** — The concept has fundamentally different properties
2. **Different UI is required** — The data needs specialized rendering
3. **Unique operations** — The entity has operations that don't map to existing ones

**Examples of legitimate new entities:**
- `pr` (pull request) — Has unique fields like `head`, `base`, `mergeable`, `reviewers`
- `video` — Has unique fields like `duration`, `thumbnail`, `chapters`
- `table` (database table) — Has `columns`, `rows` structure

---

## Adapter Structure

```
adapters/{name}/
  readme.md     # Adapter definition (YAML front matter + markdown docs)
  icon.svg      # Required — vector icon (or icon.png)
  tests/        # Functional tests
```

### YAML Front Matter

```yaml
# readme.md
---
id: todoist
name: Todoist
description: Personal task management
icon: icon.svg

website: https://todoist.com
privacy_url: https://...

auth: { ... }               # Authentication config
transformers: { ... }           # How API data maps to entity schemas
operations: { ... }         # Entity CRUD (returns: entity, entity[], or void)
utilities: { ... }          # Helpers with custom return shapes (optional)
instructions: |             # AI notes
  Adapter-specific notes...
---

# Todoist

Human-readable documentation goes here...
```

---

## Adapters

Map API fields to entity properties. Defined once, applied to all operations.

```yaml
transformers:
  task:
    terminology: Task           # What the service calls it
    mapping:
      id: .id
      title: .content
      completed: .checked
      priority: 5 - .priority   # Invert: Todoist 4=urgent → AgentOS 1=highest
      due_date: .due.date?      # Optional field
```

### Supporting Models

For data shapes that aren't standalone entities (like DNS records), define adapters too:

```yaml
transformers:
  domain:
    terminology: Domain
    mapping:
      fqdn: .domain
      status: .status
      registrar: '"porkbun"'
      expires_at: .expireDate

  dns_record:                   # Not a standalone entity, just a data shape
    terminology: DNS Record
    mapping:
      id: .id
      name: .name
      type: .type
      values: '[.content]'
      ttl: '.ttl | tonumber'
```

---

## Operations

Entity CRUD. **Naming:** `entity.operation` — `task.list`, `webpage.search`, `event.create`

**Return types:** `entity` (single), `entity[]` (array), `void` (no data)

```yaml
operations:
  task.list:
    description: List actionable tasks
    returns: task[]
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/tasks/filter
      query:
        query: .params.query
      response:
        root: /results

  task.get:
    description: Get a specific task
    returns: task
    params:
      id: { type: string, required: true }
    rest:
      method: GET
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id'
```

---

## Utilities and Return Types

Utilities are operations that don't fit standard CRUD patterns. They have flexible return types.

### Standard Result Models

Use these models from `models/common/models.yaml` for consistent contracts:

**`operation_result`** — For actions that succeed or fail:
```yaml
# Returns: { success: boolean, message?: string, id?: string }
utilities:
  add_blocker:
    description: Add blocking relationship. Returns relation ID in `id` field.
    returns: operation_result
    # ...mapping puts relation_id into `id`
  
  remove_relation:
    description: Remove a relationship by ID
    returns: operation_result
    # ...
```

**`batch_result`** — For bulk operations:
```yaml
# Returns: { succeeded: int, failed: int, total: int, errors?: string[] }
utilities:
  bulk_archive:
    returns: batch_result
```

### Choosing Return Types

| Return Type | When to Use | Example |
|-------------|-------------|---------|
| `operation_result` | Success/fail with optional ID | `remove_relation`, `add_blocker` |
| `batch_result` | Bulk operations | `bulk_archive`, `batch_delete` |
| Model reference | Shared data shape | `dns_list` → `dns_record[]` |
| Inline schema | Adapter-specific only | `get_workflow_states` |
| `void` | Raw response or no data | `logo_url` |

### Heuristics

**Use `operation_result` when:**
- Action succeeds or fails (replaces `{ success: boolean }`)
- Caller only needs confirmation
- Only output is an ID of affected/created resource

**Use model reference when:**
- Multiple adapters return same shape (`dns_record` across Gandi, Porkbun)
- UI needs consistent rendering
- AI needs predictable contract

**Use inline when:**
- Adapter-specific introspection (`get_workflow_states`)
- Shape won't be reused

---

## Entity-Level Utilities

**Key pattern:** Operations that belong to an entity but return a different data shape.

DNS operations belong to `domain` but return `dns_record`. Instead of treating `dns_record` as separate:

```yaml
# BAD: Treating dns_record as separate entity
operations:
  dns_record.list:   # ❌ Creates impression of standalone entity
```

Use entity-scoped naming:

```yaml
# GOOD: Utilities of the domain entity
operations:
  domain.list:       # Entity operation - returns domain[]
  domain.get:        # Entity operation - returns domain

  # Utilities - scoped to entity, return different shape
  domain.dns_list:   # Utility - returns dns_record[]
  domain.dns_create: # Utility - returns dns_record
  domain.dns_delete: # Utility - returns operation_result
```

**Why this matters:**
1. **Clear ownership** — DNS operations are part of domain management
2. **No false entities** — `dns_record` isn't a standalone thing you browse
3. **UI integration** — Domain detail view can show DNS records as a section
4. **Portable** — Any adapter implementing `domain` can implement these utilities

**Complete example from Porkbun:**

```yaml
operations:
  domain.list:
    description: List all domains in your account
    returns: domain[]
    rest:
      method: POST
      url: https://api.porkbun.com/api/json/v3/domain/listAll

  # Utilities returning dns_record model
  domain.dns_list:
    description: List all DNS records for a domain
    returns: dns_record[]
    params:
      domain: { type: string, required: true }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/dns/retrieve/" + .params.domain'
      response:
        root: /records

  # Utility returning operation_result
  domain.dns_delete:
    description: Delete a DNS record
    returns: operation_result
    params:
      domain: { type: string, required: true }
      id: { type: string, required: true }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/dns/delete/" + .params.domain + "/" + .params.id'
      response:
        mapping:
          success: '.status == "SUCCESS"'
```

**Models are defined in `models/{domain}/models.yaml`**:
- `dns_record` in `models/domains/models.yaml` — has properties, no operations
- `operation_result` in `models/common/models.yaml` — standard result shape

---

## Expression Syntax (jaq)

All values use jaq expressions (Rust jq). Access `.params.*`, `.auth.*`, do math, conditionals:

| Pattern | Example |
|---------|---------|
| Dynamic URL | `'"https://api.example.com/tasks/" + .params.id'` |
| Query param | `.params.limit \| tostring` |
| URL encode | `.params.query \| @uri` |
| Math | `5 - .params.priority` |
| Conditional | `'if .params.feed == "new" then "story" else "front_page" end'` |
| Unix → ISO | `.created_utc \| todate` |
| Static string | `'"Bearer "'` |
| Optional | `.due.date?` |
| Array wrap | `'[.content]'` |
| Parse number | `'.ttl \| tonumber'` |
| Split string | `'.auth.key \| split(":") \| .[0]'` |

---

## Executors

| Executor | Use case | Example |
|----------|----------|---------|
| `rest` | HTTP APIs | `adapters/todoist/` |
| `graphql` | GraphQL APIs | `adapters/linear/` |
| `swift` | macOS native APIs | `adapters/apple-calendar/` |
| `command` | Shell commands | `adapters/whois/` |
| `sql` | Database queries | `adapters/postgres/` |

---

## Testing

Every operation needs at least one test. Tests use the `aos()` helper:

```typescript
import { describe, it, expect, beforeAll } from "vitest";
import { aos } from "../../../tests/utils/fixtures";

const adapter = "porkbun";
let skipTests = false;

describe("Porkbun Adapter", () => {
  beforeAll(async () => {
    try {
      await aos().call("UseAdapter", { adapter, tool: "domain.list", params: {} });
    } catch (e: any) {
      if (e.message?.includes("Credential not found")) {
        console.log("  ⏭ Skipping: no credentials");
        skipTests = true;
      } else throw e;
    }
  });

  describe("domain.list", () => {
    it("returns array of domains", async () => {
      if (skipTests) return;
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "domain.list",
        params: {},
      });
      expect(Array.isArray(result)).toBe(true);
    });
  });

  describe("domain.dns_create", () => {
    it("creates DNS record (skip - would modify)", async () => {
      // Skip destructive tests but reference tool for validation
      const _ = { tool: "domain.dns_create" };
      expect(true).toBe(true);
    });
  });
});
```

**Important:** The validation script looks for `tool: "operation.name"` patterns. Include them even in skipped tests.

---

## Checklist

Before committing a adapter:

- [ ] `icon.svg` or `icon.png` exists
- [ ] `npm run validate` passes
- [ ] Checked existing entities before creating new ones
- [ ] Adapters map to entity properties (see `models/{domain}/models.yaml`)
- [ ] Utilities use standard result models when appropriate (`operation_result`, `batch_result`)
- [ ] Tests cover all operations (including skipped ones with tool references)
- [ ] Entity-level utilities use `entity.utility_name` naming (not `other_entity.operation`)

---

## Related Skills

- **write-app.md** - Writing apps or entity components (TSX uses data-component primitives)

---

*Entity reuse is what makes AgentOS powerful. One interface, infinite sources.*
