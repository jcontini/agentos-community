# Contributing to AgentOS Integrations

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  APPS: Tasks • Books • Messages • Calendar • Contacts • Finance    │
│  Location: apps/{app}/readme.md                                     │
│    - Schema: data contract                                          │
│    - Actions: what the app can do + readonly flag                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  INTEGRATIONS: linear • todoist • apple-contacts • mimestream       │
│  Location: apps/{app}/connectors/{name}/readme.md                   │
│    - Auth config + action implementations                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  EXECUTORS: rest • graphql • sql • swift • applescript • csv • ... │
│  (Built into AgentOS Core - you configure them in YAML)            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Terminology

| Term | Meaning |
|------|---------|
| **App** | Data type with unified schema + actions (tasks, contacts, email) |
| **Integration** | Service that implements app(s) — formerly "Connector" |
| **Account** | Your configured access to an integration |
| **Executor** | Protocol handler: `rest:`, `sql:`, `graphql:`, `swift:`, etc. |

> We're migrating terminology from "Connector" to "Integration". Folder structure still uses `connectors/` but prefer "integration" in documentation and new code.

---

## ⚠️ Key Concepts (Read First!)

### 1. `readonly` is defined at APP level, not integration

Write protection comes from `apps/{app}/readme.md`, NOT the integration:

```yaml
# apps/contacts/readme.md  ← THIS is where readonly goes
actions:
  list:
    description: List contacts
    readonly: true  # ← Controls write protection
```

If you get error `'action' is a write action`, add the action to the **app's** readme.md with `readonly: true`.

### 2. Template defaults need `| default:` syntax

The YAML `default:` on params does NOT auto-apply in templates:

```yaml
# ❌ WRONG - params.sort will be empty string if not provided
ORDER BY CASE '{{params.sort}}' WHEN 'modified' THEN ...

# ✅ CORRECT - defaults to 'modified' in the template itself
ORDER BY CASE '{{params.sort | default: modified}}' WHEN 'modified' THEN ...
```

### 3. Restart AgentOS after YAML changes

```bash
./restart.sh cursor    # Toggle MCP config to force reload
# OR
pkill -9 agentos       # Kill process, will restart on next call
```

---

## Quick Reference

| To build... | Reference integration |
|-------------|---------------------|
| REST API | `apps/finance/connectors/copilot/readme.md` |
| GraphQL API | `apps/tasks/connectors/linear/readme.md` |
| Local SQLite + AppleScript | `apps/contacts/connectors/apple-contacts/readme.md` |
| macOS Swift (EventKit, etc) | `apps/calendar/connectors/apple-calendar/readme.md` |
| Browser automation | `apps/messages/connectors/instagram/readme.md` |
| CSV import | `apps/books/connectors/goodreads/readme.md` |

---

## Executors

### `sql:` — Database Queries

**Reference:** `apps/contacts/connectors/apple-contacts/readme.md`

```yaml
sql:
  database: "~/Library/Messages/chat.db"
  query: |
    SELECT * FROM message 
    WHERE text LIKE '%{{params.query}}%'
    LIMIT {{params.limit | default: 50}}
  response:
    mapping:
      id: "[].ROWID"
      text: "[].text"
```

**Key points:**
- `database:` path supports templates: `"~/path/{{params.account}}/file.db"`
- Use `| default:` in templates for default values
- Glob patterns work: `"~/Sources/*/file.db"` queries ALL matches and merges results
- For single-database queries, use explicit path (better for LIMIT accuracy)

---

### `swift:` — macOS Native APIs

**Reference:** `apps/calendar/connectors/apple-calendar/readme.md`

```yaml
swift:
  script: |
    import Contacts
    import Foundation
    
    let store = CNContactStore()
    // ... Swift code here ...
    
    // Output JSON to stdout
    print(jsonString)
  response:
    mapping:
      id: "[].id"
      name: "[].name"
```

**Key points:**
- Scripts are compiled once and cached in `~/.agentos/cache/swift/`
- Clear cache if changes aren't taking effect: `rm -rf ~/.agentos/cache/swift/*`
- Output JSON to stdout, errors to stderr
- Use for: EventKit (Calendar), CNContactStore (Contacts metadata), HealthKit, etc.

**Apple ID gotcha:** CNContactStore returns IDs like `ABC-123:ABAccount` but filesystem uses just `ABC-123`:
```swift
let dirId = container.identifier.replacingOccurrences(of: ":ABAccount", with: "")
```

---

### `applescript:` — macOS Automation

**Reference:** `apps/contacts/connectors/apple-contacts/readme.md`

```yaml
applescript:
  script: |
    tell application "Contacts"
      set p to make new person with properties {first name:"{{params.first_name}}"}
      save
      return "{\"id\":\"" & id of p & "\",\"status\":\"created\"}"
    end tell
  response:
    mapping:
      id: ".id"
      status: ".status"
```

**Key points:**
- Best for writes that need iCloud sync (Contacts, Reminders)
- Return JSON string from AppleScript
- Slower than SQL but more reliable for writes

---

### `rest:` — REST APIs

**Reference:** `apps/finance/connectors/copilot/readme.md`

```yaml
rest:
  method: POST
  url: "https://api.example.com/items/{{params.id}}"
  headers:
    X-Custom: "value"
  body:
    field: "{{params.value}}"
  response:
    mapping:
      id: ".id"
      title: ".name"
```

**Key points:**
- Templates work in `url`, `headers`, `body`, `query`
- Auth headers injected automatically from integration auth config

---

### `graphql:` — GraphQL APIs

**Reference:** `apps/tasks/connectors/linear/readme.md`

```yaml
graphql:
  query: |
    query($id: ID!) {
      item(id: $id) { id name status }
    }
  variables:
    id: "{{params.id}}"
  response:
    root: "data.item"
    mapping:
      id: ".id"
      title: ".name"
```

**Key points:**
- Always test queries in the API's GraphQL console first (most have one)
- Check if fields return arrays vs objects — don't assume (e.g., some APIs return `me` as `[{...}]` not `{...}`)
- For chained queries, see "Chained Executors" section below — intermediate steps need `.data.` in paths

---

### `csv:` — CSV File Parsing

**Reference:** `apps/books/connectors/goodreads/readme.md`

```yaml
csv:
  path: "{{params.path}}"
  response:
    mapping:
      title: "[].'Book Title'"
      rating: "[].'My Rating' | to_int"
```

---

### `playwright:` — Browser Automation

**Reference:** `apps/messages/connectors/instagram/readme.md`

Used for cookie-based auth and services without APIs:

```yaml
auth:
  type: cookies
  domain: instagram.com
  cookies: [sessionid, csrftoken]
  connect:
    playwright:
      launch:
        headless: false
      steps:
        - goto: "https://instagram.com/login"
        - wait_for:
            url_matches: "https://instagram.com/"
            timeout: 300000
        - extract_cookies:
            names: [sessionid, csrftoken]
```

---

### Chained Executors

Chain multiple steps with `as:` to name outputs:

```yaml
actions:
  complete:
    - graphql:
        query: "{ issue(id: $id) { team { states { nodes { id } } } } }"
        variables: { id: "{{params.id}}" }
      as: lookup
    
    - graphql:
        query: "mutation { issueUpdate(id: $id, input: $input) { success } }"
        variables:
          id: "{{params.id}}"
          input:
            stateId: "{{lookup.data.issue.team.states.nodes[0].id}}"
```

**Accessing chained results by executor type:**

| Executor | Result structure | Access pattern |
|----------|------------------|----------------|
| `graphql:` | Object with `data` | `{{step.data.field}}` |
| `sql:` | Array of rows | `{{step[0].column}}` (first row) |
| `command:` | stdout string directly | `{{step}}` (NOT `{{step.stdout}}`) |

**Common gotchas:**

1. **SQL returns an array** — use bracket notation `{{contact[0].name}}`:
```yaml
# ❌ WRONG - contact is an array
'{{contact.name}}'

# ✅ CORRECT - bracket notation for array index
'{{contact[0].name}}'
```

2. **Command returns stdout directly** — NOT wrapped in an object:
```yaml
# ❌ WRONG - command result is just the stdout string
'{{photo.stdout}}'

# ✅ CORRECT - access directly
'{{photo}}'
```

3. **GraphQL intermediate steps keep the full response** — include `.data.` in paths:
```yaml
# Step 1: Get user info
- graphql:
    query: "{ me { id } }"
  as: user

# Step 2: Use the ID
- graphql:
    variables:
      # ❌ WRONG - missing .data. wrapper
      user_id: "{{user.me.id}}"
      
      # ✅ CORRECT - include .data. from GraphQL response
      user_id: "{{user.data.me.id}}"
```

4. **Some APIs return arrays where you expect objects** — always verify the actual response:
```yaml
# Many APIs return "me" as a single object:
#   { "data": { "me": { "id": 123 } } }
# Access: {{user.data.me.id}}

# But some (like Hardcover) return an array:
#   { "data": { "me": [{ "id": 123 }] } }
# Access: {{user.data.me[0].id}}
```

5. **Unresolved templates become null and get removed** — if you see errors like `"expecting a value for non-nullable variable"`, the template path is wrong:
```yaml
# This error means {{user.data.me.id}} resolved to nothing
# Debug by checking:
#   1. Is the first step actually succeeding?
#   2. Is the path correct? (check API docs for actual response structure)
#   3. Does the API return an array instead of an object?
```

**Testing chained executors:** Always test with real data that returns results. Template variables like `{{step}}` will appear literally in output if the step returned empty/null — tests with empty results won't catch this!

**Debugging tips:**
- Check `~/.agentos/data/agentos.db` activity_log table to see what succeeded/failed
- Look for GraphQL APIs that have interactive consoles to test queries directly
- When in doubt, check the reference integrations (Linear for GraphQL, apple-contacts for SQL)

---

## macOS Integration Pattern

For local macOS data, use mixed executors:

| Task | Executor | Why |
|------|----------|-----|
| List accounts/containers | `swift:` | Only way to get CNContactStore/EKEventStore metadata |
| Fast reads | `sql:` | Direct SQLite is 10-100x faster |
| Reliable writes | `applescript:` | Syncs properly with iCloud |

**Example:** `apps/contacts/connectors/apple-contacts/readme.md` uses:
- `swift:` for `accounts` action (list containers)
- `sql:` for `list`, `search` (fast indexed queries)
- `applescript:` for `create`, `update`, `delete`, `set_photo` (iCloud sync)

---

## Response Mapping

```yaml
response:
  root: "data.items"       # Where to find data in response
  mapping:
    id: "[].id"            # Array iteration
    title: "[].name"
    rating: "[].score | to_int"
    connector: "'myconnector'"  # Static value (note quotes)
```

**Transforms:** `to_int`, `to_array`, `trim`, `strip_quotes`, `split:,`, `default:value`

---

## Creating an App

**Location:** `apps/{app}/readme.md`

```yaml
---
id: contacts
name: Contacts
schema:
  contact:
    id: { type: string, required: true }
    first_name: { type: string }
    # ...

actions:
  list:
    description: List contacts
    readonly: true  # ← READ-ONLY actions
    params:
      limit: { type: number, default: 50 }
    returns: contact[]
  
  create:
    description: Create contact
    # No readonly = WRITE action (requires execute: true)
    params:
      first_name: { type: string }
---
```

---

## Creating an Integration

**Location:** `apps/{app}/connectors/{name}/readme.md`

```yaml
---
id: apple-contacts
name: Apple Contacts

# Auth (optional - omit for local integrations)
auth:
  type: api_key
  header: Authorization

# Action implementations
actions:
  list:
    sql:
      database: "~/Library/AddressBook/..."
      query: "SELECT * FROM ..."
---
```

---

## Testing

See [TESTING.md](./TESTING.md) for full guide.

```typescript
import { aos, testContent } from '../../../tests/utils/fixtures';

describe('My Integration', () => {
  it('can list items', async () => {
    const items = await aos().call('MyApp', {
      action: 'list',
      connector: 'my-connector',
      params: { limit: 5 }
    });
    expect(items.length).toBe(5);
  });
});
```

**Test data convention:** Use `[TEST]` prefix via `testContent('name')` → `"[TEST] name abc123"`

---

## File Structure

```
apps/
  contacts/
    readme.md           ← App schema + actions + readonly flags
    icon.svg
    connectors/
      apple-contacts/
        readme.md       ← Integration auth + action implementations
        icon.png
    tests/
      contacts.test.ts
```
