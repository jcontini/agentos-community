# Contributing to AgentOS Community

Everything lives here — entities, skills, apps, and themes. Core (`agentos`) is a generic Rust engine; this repo is the ecosystem.

In development, the server points directly at this repo (`~/dev/agentos-community`). Edits are live after a server restart. Core embeds a snapshot at build time; the community version overrides it.

| Concern | Directory | What it is |
|---------|-----------|-----------|
| **Entities** | `entities/` | The Memex model — what things ARE |
| **Skills** | `skills/` | Service connections + agent instructions |
| **Apps** | `apps/` | UI experiences (Videos, Memex, Settings, etc.) |
| **Themes** | `themes/` | Visual styling (CSS) |

---

## Guides

Read the relevant guide before starting work:

| Guide | When to Use |
|-------|-------------|
| This file (`CONTRIBUTING.md`) | **Default.** Writing, updating, or fixing skills |
| `skills/write-app.md` | Writing apps or entity components |
| `skills/shell-history.md` | Querying shell history |
| `skills/apple-biome.md` | Screen time, app usage, media playback, location |

---

## Quick Start

```bash
# 1. Edit directly in this repo (it's the live source)
vim skills/my-skill/readme.md

# 2. Restart AgentOS server and test
cd ~/dev/agentos && ./restart.sh
curl http://localhost:3456/mem/tasks?skill=my-skill

# 3. Validate and commit
npm run validate
git add -A && git commit -m "Add my-skill"
```

---

## Commands

```bash
npm run validate             # Schema validation + test coverage (run first!)
npm test                     # Functional tests (excludes .needs-work)
npm run test:needs-work      # Test skills in .needs-work
npm test skills/exa/tests    # Test specific skill
npm run new-skill <name>     # Create skill scaffold
```

| Command | What it checks |
|---------|----------------|
| `npm run validate` | Schema structure, test coverage, required files (icon.svg) |
| `npm test` | Actually calls APIs, verifies behavior |

**Always run `npm run validate` first** — it catches structural issues before you test.

---

## Folder Structure

Every skill is a folder inside `skills/`:

```
skills/
  my-service/
    readme.md     <- Skill definition (YAML front matter + markdown docs)
    icon.svg      <- Required. Vector icon, or icon.png if no SVG available.
    tests/
      my-service.test.ts
```

---

## YAML Front Matter

The `readme.md` must start with a YAML front matter block between `---` delimiters.

### Required fields

```yaml
id: my-service              # lowercase, hyphenated, unique in the repo
name: My Service            # Display name
description: One-line description of what this skill connects to
icon: icon.svg
```

### Common optional fields

```yaml
color: "#FF4500"            # Brand hex color
website: https://myservice.com
privacy_url: https://myservice.com/privacy
auth: none                  # or an auth config block (see Auth section)
platforms: [macos]          # Limit to specific platforms if needed
connects_to: my-service     # Seed entity ID this skill connects to
instructions: |             # AI guidance for using this skill
  Notes for the agent about how to use this skill well.
```

---

## Auth

The auth block is a template. It declares where credential fields go in HTTP requests
using `{placeholder}` syntax. Three injection points: `header`, `query`, `body` — each
is a map of name → value with placeholders.

Placeholders are extracted to drive the UI form (one password input per unique placeholder).
Credentials are stored as `{ fields: { "placeholder": "value" } }`.

### No auth
```yaml
auth: none
```

### Header auth (most common — Bearer token, API key header)
```yaml
auth:
  header:
    Authorization: "Bearer {token}"
  label: API Key
  help_url: https://myservice.com/api-keys
```

Custom header names work too:
```yaml
auth:
  header:
    X-API-Key: "{token}"
```

### Query param auth
```yaml
auth:
  query:
    api_key: "{token}"
  label: API Key
  help_url: https://myservice.com/api-keys
```

### Body auth (multi-field)

For APIs that require credentials in the request body. Each placeholder becomes
a separate input field in the UI:

```yaml
auth:
  body:
    apikey: "{apikey}"
    secretapikey: "{secretapikey}"
  label: API Keys
  help_url: https://myservice.com/api-keys
```

### Combined injection

Header + query + body can be combined if needed:
```yaml
auth:
  header:
    Authorization: "Bearer {token}"
  query:
    org_id: "{org_id}"
```

### Optional auth (skill works anonymously, better with credentials)
```yaml
auth:
  header:
    Authorization: "Bearer {token}"
  optional: true    # Don't block operations if no credentials — anonymous mode
  label: API Key
  help_url: https://myservice.com/api-keys
```

Use `optional: true` when a service has anonymous access but authenticated users get
higher rate limits, persistence, or additional features. Operations still run without
credentials — the auth header is simply omitted.

### Per-operation `auth: none` override

For public endpoints inside an otherwise-authenticated skill — e.g. a signup utility
that sends a magic link before the user has credentials:

```yaml
utilities:
  signup:
    auth: none    # Skip credential check for this operation only
    params:
      email: { type: string, required: true }
    returns:
      sent: boolean
    rest:
      method: POST
      url: '"https://api.myservice.com/auth/magic-link"'
      body:
        email: .params.email
```

`auth: none` works on both `operations:` and `utilities:` entries, for any executor
(rest, graphql, command, etc.). It completely skips credential resolution and header
injection for that one operation. Without it, any skill with `auth:` configured will
block all calls — including signup — until credentials exist.

### Auth in command/jq templates

For command and jq executors, credential fields are also available as template variables:
- `{{auth.key}}` — the primary token (for single-field credentials)
- `{{auth.fieldname}}` — a specific credential field by name
- `.auth.key` / `.auth.fieldname` — same, in jq syntax

---

## Transformers

Transformers map API response fields to entity schema properties. Define once, applied
to all operations that return that entity type.

```yaml
transformers:
  task:
    terminology: Task         # What this service calls it (for UI labels)
    mapping:
      id: .id
      title: .content
      completed: .checked
      priority: 5 - .priority # Invert: service 4=urgent -> AgentOS 1=highest
      due_date: .due.date?    # Optional field
      url: '"https://myservice.com/task/" + .id'
```

### Mapping adapter-specific fields with `data.*`

Entity schemas have a `data` bag for adapter-specific fields that don't belong in the
shared schema. Map into it directly using dotted keys:

```yaml
transformers:
  task:
    mapping:
      id: .id
      title: .title
      data.remote_id: .identifier      # Service's own human-readable ID (e.g., "AGE-123")
      data.status: .state.name         # Service-specific status label
      data.url: .url                   # Deep link back into the service
      data.assignee.id: '(.assignee // {}).id'    # Nested object in data bag
      data.assignee.name: '(.assignee // {}).name'
```

The `data.*` pattern stores the value at `entity.data.remote_id`, `entity.data.assignee`, etc.
Use this for anything that's useful for agents but not part of the cross-service entity schema.

### Rich Content (entity bodies)

Use `content` to store long-form text (descriptions, transcripts, markdown) separately
from structured fields. It's indexed in full-text search.

```yaml
transformers:
  post:
    mapping:
      id: .id
      title: .title
      content: .body_html        # stored in entity_bodies, FTS-indexed
```

If an entity can have multiple bodies (e.g. a video with description AND transcript):

```yaml
transformers:
  video:
    mapping:
      id: .id
      title: .title
      content: .transcript_text
      content_role: '"transcript"'   # role key in entity_bodies (default: "body")
```

**Rules:**
- `content` is reserved — not stored in entity data, routed to `entity_bodies`
- `content_role` sets the role (default `"body"`). Use when an entity has more than one body
- Both are stripped from entity data before storage — don't also map them to a schema property

### Supporting Models

For data shapes returned by a skill that aren't standalone entities (like DNS records),
define a transformer without the entity needing its own operations:

```yaml
transformers:
  domain:
    terminology: Domain
    mapping:
      fqdn: .domain
      status: .status
      registrar: '"porkbun"'
      expires_at: .expireDate

  dns_record:               # Not a standalone entity — just a data shape
    terminology: DNS Record
    mapping:
      id: .id
      name: .name
      type: .type
      values: '[.content]'
      ttl: '.ttl | tonumber'
```

Operations can then declare `returns: dns_record[]` and the transformer is applied.

### Choosing the right entity type

Always map to an existing entity before creating a new one. Check `entities/{type}.yaml`
in the community repo for exact property names. Common types:
`task`, `person`, `message`, `conversation`, `post`, `video`, `channel`, `document`,
`meeting`, `forum`, `webpage`, `website`, `repository`, `domain`, `tag`

Only create a new entity type if no existing type fits. Good reasons:
- Fundamentally different properties (e.g., `pull_request` has `head`, `base`, `mergeable`)
- Needs different UI rendering
- Has unique operations that don't fit existing patterns

---

## Operations

Entity CRUD. Naming: `entity.operation` — `task.list`, `message.send`, `video.search`

```yaml
operations:
  task.list:
    description: List tasks
    returns: task[]
    rest:
      method: GET
      url: https://api.myservice.com/tasks
      response:
        root: /results        # JSON pointer to array in response

  task.get:
    description: Get a specific task by ID
    returns: task
    params:
      id: { type: string, required: true }
    rest:
      method: GET
      url: '"https://api.myservice.com/tasks/" + .params.id'

  task.create:
    description: Create a new task
    returns: task
    params:
      title: { type: string, required: true }
      due_date: { type: string }
    rest:
      method: POST
      url: https://api.myservice.com/tasks
      body:
        content: .params.title
        due: { date: .params.due_date }
```

### Return types

| Return | When |
|--------|------|
| `entity[]` | List / search operations |
| `entity` | Get / create / update operations |
| `void` | Delete or mutation with no useful return value |

Use `void` for any operation that doesn't return an entity. For richer return shapes
(success flags, IDs, custom data), use `utilities:` instead — see the Utilities section.

### Valid operation suffixes

The validator knows these suffixes and enforces their return types:
`list`, `get`, `create`, `update`, `delete`, `search`, `pull`, `archive`

**Any other suffix in `operations:` will be treated as a read and must return an entity.**
If you need an action like `claim`, `assign`, `transfer`, or `check` — put it in
`utilities:` (see below), not in `operations:`.

### Executors

| Executor | Use case | Example skill |
|----------|----------|---------------|
| `rest` | HTTP REST APIs | `todoist`, `exa` |
| `graphql` | GraphQL APIs | `linear` |
| `sql` | SQLite/Postgres queries | `imessage`, `postgres` |
| `command` | CLI tools, local scripts | `youtube`, `granola` |
| `swift` | macOS native frameworks | `apple-calendar` |
| `applescript` | macOS automation | |
| `csv` | Parse CSV files/data | |
| `keychain` | macOS Keychain access | |
| `crypto` | PBKDF2 key derivation, AES-128-CBC decryption | |
| `steps` | Multi-step pipelines — chain executors | |

**Planned executors (not yet implemented):**

| Executor | Use case |
|----------|----------|
| `oauth` | OAuth2 authorization code flow, token refresh |

### Command Executor

Runs a local binary with arguments. Output is parsed as JSON (falls back to string).

```yaml
operations:
  video.search:
    description: Search YouTube videos
    returns: video[]
    params:
      query: { type: string, required: true }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "yt-dlp --flat-playlist --dump-json 'ytsearch10:{{params.query}}' 2>/dev/null | jq -s '.'"
      timeout: 60
```

| Field | Type | Description |
|-------|------|-------------|
| `binary` | string | Binary name (resolved via PATH + common dirs) |
| `args` | string[] | Arguments array — each element interpolated with `{{params.x}}` |
| `args_string` | string | Alternative: single string split on whitespace |
| `stdin` | string | Content piped to stdin — use for large inputs instead of args |
| `timeout` | integer | Timeout in seconds (default: 60) |
| `working_dir` | string | Working directory (interpolated, supports `~/`) |
| `response` | object | Response mapping (same as REST — root, mapping) |

**Credentials in command args:** Use `{{auth.key}}` to inject the resolved credential
into args or stdin. The engine resolves it from the AgentOS credential store before
template rendering — it's available the same way as `{{params.x}}`:

```yaml
operations:
  website.create:
    returns: website
    params:
      content: { type: string, required: true }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/skills/publish.py --token '{{auth.key}}'"
      stdin: "{{params.content}}"
```

If credentials aren't configured and the skill has `optional: true` auth, `{{auth.key}}`
renders as an empty string — scripts should handle that gracefully.

**Tips:**
- Use `bash -l -c "..."` to get a login shell (loads PATH, homebrew, pyenv, etc.)
- Python scripts should `print(json.dumps(result))` — executor parses stdout as JSON
- Pass large content (HTML, file data) via `stdin:` rather than args to avoid shell quoting
- Use `2>/dev/null` to suppress stderr noise from CLI tools
- Use `{{#if params.x}} --flag '{{params.x}}'{{/if}}` for optional string args
- Avoid `{{#if}}` for integer/boolean params — falsy values (`0`, `false`) may not skip

### Keychain Executor

Reads entries from the macOS Keychain (or platform-native secure storage) via the `keyring` crate.
Returns `{"value": "..."}`.

```yaml
operations:
  key.get:
    description: Get Chrome Safe Storage key
    returns: credential
    keychain:
      service: "Chrome Safe Storage"
      account: "Chrome"   # optional, defaults to $USER
```

| Field | Type | Description |
|-------|------|-------------|
| `service` | string | Keychain service name (e.g., "Chrome Safe Storage") |
| `account` | string | Account name (optional, defaults to current user, supports `$USER`) |
| `response` | object | Response mapping |

### Crypto Executor

Generic cryptographic primitives. Two algorithms:

**PBKDF2-HMAC-SHA1** — key derivation:
```yaml
crypto:
  algorithm: pbkdf2
  password: "{{get_key.value}}"
  salt: "saltysalt"
  iterations: 1003
  key_length: 16
```

**AES-128-CBC** — decryption with PKCS7 padding:
```yaml
crypto:
  algorithm: aes-128-cbc
  key: "{{derive.value}}"
  iv: "20202020202020202020202020202020"
  data: "{{raw_cookies.encrypted_value}}"
```

| Field | Type | Description |
|-------|------|-------------|
| `algorithm` | string | `"pbkdf2"` or `"aes-128-cbc"` |
| `password` | string | PBKDF2: password input (template-interpolated) |
| `salt` | string | PBKDF2: salt string |
| `iterations` | integer | PBKDF2: iteration count |
| `key_length` | integer | PBKDF2: output key length in bytes |
| `key` | string | AES: hex-encoded 16-byte key (template-interpolated) |
| `iv` | string | AES: hex-encoded 16-byte IV (template-interpolated) |
| `data` | string | AES: hex-encoded ciphertext (template-interpolated) |
| `response` | object | Response mapping |

Both algorithms return `{"value": "hex_string"}`.

### Steps Executor

Multi-step pipelines that chain executors sequentially. Each step has an `id`, uses any
executor, and can reference previous step outputs via `{{step_id.field}}`.

```yaml
operations:
  credential.get:
    description: Extract encrypted cookies from Chrome
    params:
      domain: { type: string, required: true }
    returns: credential
    steps:
      - id: get_key
        keychain:
          service: "Chrome Safe Storage"

      - id: derive
        crypto:
          algorithm: pbkdf2
          password: "{{get_key.value}}"
          salt: "saltysalt"
          iterations: 1003
          key_length: 16

      - id: raw_cookies
        sql:
          database: "~/Library/Application Support/Google/Chrome/Default/Cookies"
          query: "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE :domain"
          params:
            domain: ".{{params.domain}}"

      - id: decrypt
        crypto:
          algorithm: aes-128-cbc
          key: "{{derive.key}}"
          iv: "20202020202020202020202020202020"
          data: "{{raw_cookies.rows}}"
```

**Step fields:**
- `id` — required, used to reference this step's output in later steps
- Any executor key (`rest`, `sql`, `command`, `keychain`, `crypto`, etc.)
- `skip_if` — conditional skip (Handlebars expression)

Each step's output is stored in a context map. Later steps access it via `{{step_id.field}}`.
The final step's output becomes the operation's return value.

---

## How Data Flows: Graph-First

AgentOS is **graph-first**. Skills sync data INTO the Memex; queries read FROM it.

```
Skill (API/command) -> extract + transform -> Memex (SQLite) -> REST/MCP response
```

**Default list requests read from cache — they do NOT call skills.**

| Request | What happens |
|---------|-------------|
| `GET /mem/tasks` | Reads cached graph. Fast (0ms). No skill execution. |
| `GET /mem/tasks?refresh=true` | Syncs ALL task skills first, then reads graph. |
| `GET /mem/tasks?refresh=true&skill=todoist` | Syncs only Todoist, then reads graph. |

**`?refresh=true` is how you trigger a live pull.** Without it, you only see what was previously synced.

```bash
# First sync: pulls data from your skill into the graph
curl -H "X-Agent: test" "http://localhost:3456/mem/tasks?refresh=true&skill=my-service"

# Subsequent reads: fast, from cache
curl -H "X-Agent: test" "http://localhost:3456/mem/tasks"

# Direct skill call (bypasses graph, returns live data)
curl -X POST "http://localhost:3456/use/my-service/task.list" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

---

## Expression Syntax

Skills use **two syntaxes** depending on the executor:

### REST / GraphQL operations — jaq expressions (jq syntax)

```yaml
# jaq expressions — used in rest: and graphql: blocks
url: '"https://api.example.com/tasks/" + .params.id'
query:
  limit: .params.limit | tostring
  priority: 5 - .params.priority
body:
  content: .params.title
  due: { date: .params.due_date }
```

**Common jaq patterns:**
- String concat: `'"https://example.com/" + .params.id'`
- To string: `.params.limit | tostring`
- URL encode: `.params.query | @uri`
- Unix -> ISO: `.created_utc | todate`
- Optional: `.due.date?`
- Conditional: `'if .params.x == "y" then "a" else "b" end'`
- Math: `5 - .params.priority`

### Command executor — Handlebars templates

```yaml
# Template syntax — used in command: args, stdin, and working_dir
command:
  binary: bash
  args:
    - "-l"
    - "-c"
    - "yt-dlp --dump-json '{{params.url}}' 2>/dev/null"
  stdin: "{{params.content}}"
```

**Template patterns:**
- Simple value: `{{params.query}}`
- Auth credential: `{{auth.key}}`
- Default value: `{{params.limit | default:10}}`
- Conditional flag: `{{#if params.title}} --title '{{params.title}}'{{/if}}`

---

## Credits

The `credits` field is the unified place for attribution and dependency declaration.
If your skill needs or is inspired by something, it goes here. There's no separate
`needs` or `desires` section — crediting forces attribution.

```yaml
credits:
  - entity: repository          # An entity capability this skill needs
    operations: [write]
    relationship: needs         # Required to function
  - entity: webpage
    operations: [read]
    relationship: desires       # Optional but better with it
  - skill: git
    relationship: appreciates   # Attribution / inspiration
    reason: Shared patterns for working with git repositories
```

### Relationship types

| Relationship | Meaning |
|-------------|---------|
| `needs` | Required — skill won't work without this entity capability |
| `desires` | Optional — better experience if installed |
| `appreciates` | Attribution — this influenced or inspired the skill |

**Entity vs skill credits:**
- Use `entity` + `operations` when you need a *capability* (runtime resolves what provides it)
- Use `skill` when you're attributing or relating to a *specific skill*

---

## Seed Entities

Seed entities are graph nodes created on skill load. Use them to credit upstream projects,
declare what service the skill connects to, and model the maintainers behind it.

```yaml
seed:
  - id: my-service
    types: [software]
    name: My Service
    data:
      software_type: api        # api | cli | app | service | library
      url: https://myservice.com
      launched: "2020"
      platforms: [web]
      pricing: freemium         # free | freemium | paid | open_source
    relationships:
      - role: offered_by
        to: my-service-org

  - id: my-service-org
    types: [organization]
    name: My Service Inc.
    data:
      type: company
      url: https://myservice.com
```

Always create a seed entity for:
- The service this skill connects to
- Any CLI tool, library, or upstream dependency the skill wraps
- The author/organization behind critical dependencies

---

## Utilities

For operations that don't fit standard entity CRUD — introspection, actions, setup flows,
custom return shapes. Use utilities when:
- The return isn't an entity (workflow states, org info, success flags)
- The action verb isn't in the standard operation set (`claim`, `assign`, `transfer`, `setup`)
- You need a mutation that returns a custom shape

```yaml
utilities:
  get_workflow_states:
    description: List available workflow states for a team
    params:
      team_id: { type: string, required: true }
    returns:
      id: string
      name: string
      type: string
    rest:
      method: GET
      url: '"https://api.myservice.com/teams/" + .params.team_id + "/states"'
      response:
        root: /states

  add_blocker:
    description: Add a blocking relationship between two issues
    params:
      id: { type: string, required: true }
      blocker_id: { type: string, required: true }
    returns: void
    rest:
      method: POST
      url: https://api.myservice.com/relations
      body:
        issueId: .params.blocker_id
        relatedIssueId: .params.id
        type: '"blocks"'

  setup:
    description: Auto-configure account params after credential is added
    returns:
      org_name: string
      teams: array
    graphql:
      query: "{ organization { name } teams { nodes { id name } } }"
      response:
        root: /data
```

**Naming rules (enforced by validator):** utility names must be `snake_case` — no dots,
no spaces. Pattern: `verb_noun` (`get_teams`, `add_blocker`, `claim_site`) or just a
noun (`setup`, `whoami`, `signup`). For credential acquisition flows, `signup` is the
conventional name — pair it with `auth: none` so it works before credentials exist.

**`returns` in utilities** can be:
- `void` — mutation with no useful output
- An inline object schema — `{ id: string, name: string }` for custom shapes
- An array — `returns: array` for list-style utilities

---

## Testing

Every operation needs at least one test. Tests use the `aos()` helper:

```typescript
import { describe, it, expect, beforeAll } from "vitest";
import { aos } from "../../../tests/utils/fixtures";

const skill = "my-service";
let skipTests = false;

describe("My Service Skill", () => {
  beforeAll(async () => {
    try {
      await aos().call("UseAdapter", { skill, tool: "task.list", params: {} });
    } catch (e: any) {
      if (e.message?.includes("Credential not found")) {
        console.log("  > Skipping: no credentials");
        skipTests = true;
      } else throw e;
    }
  });

  describe("task.list", () => {
    it("returns array of tasks", async () => {
      if (skipTests) return;
      const result = await aos().call("UseAdapter", {
        skill,
        tool: "task.list",
        params: {},
      });
      expect(Array.isArray(result)).toBe(true);
    });
  });

  // Include destructive operations in tests even if skipped — validator checks coverage
  describe("task.create", () => {
    it("creates a task (skipped — would modify data)", async () => {
      const _ = { tool: "task.create" };
      expect(true).toBe(true);
    });
  });
});
```

**Important:** The test helper calls `UseAdapter`, not `UseSkill`. The validator looks
for `tool: "operation.name"` in test files. Include every operation, even destructive
ones that are skipped.

---

## Validation & Publishing

```bash
# From the community repo root:
npm run validate              # Schema check + test coverage audit
npm test skills/my-service/tests   # Run your skill's tests

# If validate passes:
git add skills/my-service/
git commit -m "Add My Service skill"
gh pr create --title "Add My Service skill" --body "Connects AgentOS to [service]."
```

### Validation checks

- `icon.svg` or `icon.png` exists
- All required front matter fields present (`id`, `name`, `description`)
- Every operation has a test referencing `tool: "operation.name"`
- No orphaned transformers (must be referenced by at least one operation)

### PR conventions

- Title: `Add [Service] skill` or `Update [Service] skill: [what changed]`
- Include a brief description of what the service is and what operations you mapped
- Link to the service's API docs

---

## Entities

Entity schemas live in `entities/` organized by primitive type. To browse all entity types and their schemas, use `memex()` (no arguments) for an overview, or `memex({ type: "task" })` for a specific type's full schema.

**Always map to an existing entity type before creating a new one.** Only create a new type if the domain has genuinely different properties or needs different UI rendering.

When building skills, use `data.*` mapping for adapter-specific fields that don't belong in the shared schema. See the Transformers section above for details.

---

## Entity Components

**Components must only compose primitives — never custom CSS.**

```tsx
// Good: uses data-* attributes for styling
<div data-component="stack" data-direction="horizontal" data-gap="md">
  <span data-component="text" data-variant="title">{title}</span>
</div>

// Bad: custom CSS that breaks themes
<div style={{ display: 'flex', gap: '16px' }}>
  <span className="my-title">{title}</span>
</div>
```

**Why:** Themes style primitives via `[data-component="text"]` selectors. Custom CSS breaks theming.

**Image proxy:** External images need proxying to bypass hotlink protection. Import the shared helper:

```tsx
import { getProxiedSrc } from '/ui/lib/utils.js';

// getProxiedSrc handles data:, blob:, protocol-relative, and external URLs
// External URLs are rewritten to /ui/proxy/image?url=...
<img src={getProxiedSrc(item.thumbnail)} />
```

---

## Skill Checklist

Before committing a skill:

- [ ] `skills/my-service/` folder exists with `readme.md` + `icon.svg`/`icon.png`
- [ ] All required front matter: `id`, `name`, `description`, `icon`, `website`
- [ ] Auth configured correctly for the service (`optional: true` if service has anonymous access)
- [ ] Public endpoints (signup, etc.) use `auth: none` at the operation level
- [ ] `transformers` map to existing entity types (checked `entities/*.yaml`)
- [ ] Adapter-specific fields use `data.*` mapping (not polluting the entity schema)
- [ ] Operations use correct `entity.operation` naming with known suffixes only
- [ ] Actions that don't fit standard CRUD are in `utilities:` with snake_case names
- [ ] `returns: void` used for mutations/deletes; inline schema for custom shapes
- [ ] Seed entities credit the upstream service + any CLI/library dependencies
- [ ] Tests cover all operations AND utilities (even skipped destructive ones)
- [ ] `npm run validate` passes
- [ ] `npm test` passes (or gracefully skips if no credentials)

---

## The `.needs-work` Folder

Skills that fail validation live in `skills/.needs-work/`. To fix one:

1. Fix the issues
2. Run `npm run validate`
3. Move to working folder: `mv skills/.needs-work/my-skill skills/my-skill`

---

## Manifest

**Never edit `manifest.json` manually!** GitHub Actions auto-generate it on push to `main`.

```bash
node scripts/generate-manifest.js        # Regenerate
node scripts/generate-manifest.js --check # Validate only
```

---

## Key Files

| File | Purpose |
|------|---------|
| `tests/skills/skill.schema.json` | Schema source of truth for skill YAML |
| `tests/utils/fixtures.ts` | Test utilities (`aos()` helper) |
| `entities/{entity}.yaml` | Entity schema — what properties to map |

---

## License

MIT licensed. Contributions are MIT licensed and may be used in official releases including commercial offerings.
