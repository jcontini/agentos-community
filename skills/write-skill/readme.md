---
id: write-skill
name: Write Skill
description: Build, validate, and publish AgentOS community skills
icon: icon.svg
color: "#6366F1"

website: https://github.com/agentos-community/agentos-community

auth: none

credits:
  - entity: file
    operations: [read, write, edit]
    relationship: needs        # Scaffold skill files, edit YAML, create tests
  - entity: repository
    operations: [write]
    relationship: needs        # Commit and open PRs to the community repo
  - entity: webpage
    operations: [read]
    relationship: desires      # Fetch API docs when building a skill for a service
  - entity: task
    operations: [create]
    relationship: desires      # Track skill-building work in a task manager
  - skill: write-app
    relationship: appreciates
    reason: Sister skill for building apps and entity components
  - skill: code-editing
    relationship: appreciates
    reason: Provides the file operations this skill guides agents to use

instructions: |
  You are building an AgentOS skill — a YAML-defined adapter that connects an external
  service to the AgentOS entity graph. Skills live in the community repo at:
    https://github.com/jcontini/agentos-community

  When someone says "build me a [service] skill" or "improve the [skill] skill":
  1. Read this skill fully before starting.
  2. Scaffold the folder structure.
  3. Define the YAML front matter.
  4. Map API responses to entity schemas.
  5. Write tests for every operation.
  6. Validate with `npm run validate`.
  7. Submit a PR to the community repo.

  ---

  ## Folder Structure

  Every skill is a folder inside `skills/`:

  ```
  skills/
    my-service/
      readme.md     ← Skill definition (YAML front matter + markdown docs)
      icon.svg      ← Required. Vector icon, or icon.png if no SVG available.
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

  ### No auth
  ```yaml
  auth: none
  ```

  ### API key (header)
  ```yaml
  auth:
    type: api_key
    header: Authorization
    prefix: "Bearer "
    label: API Key
    help_url: https://myservice.com/api-keys
  ```

  ### API key (query param)
  ```yaml
  auth:
    type: api_key
    query: api_key
    label: API Key
  ```

  ### OAuth2 browser flow
  ```yaml
  auth:
    type: oauth2
    flow: browser
    authorize_url: https://myservice.com/oauth/authorize
    token_url: https://myservice.com/oauth/token
    scopes: [read, write]
    client_id_env: MY_SERVICE_CLIENT_ID
  ```

  ### Keychain (macOS stored credentials)
  ```yaml
  auth:
    type: keychain
    service: my-service
    fields:
      - key: username
        label: Username
      - key: password
        label: Password
        secret: true
  ```

  ### SQLite database (no auth needed — read from local DB)
  ```yaml
  database: "~/Library/Application Support/MyService/data.sqlite"
  auth: none
  ```

  ### Optional auth (skill works anonymously, better with credentials)
  ```yaml
  auth:
    type: api_key
    header: Authorization
    prefix: "Bearer "
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
        priority: 5 - .priority # Invert: service 4=urgent → AgentOS 1=highest
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
          root: /results        # JSON path to array in response

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

  ---

  ## How Data Flows: Graph-First

  AgentOS is **graph-first**. Skills sync data INTO the Memex; queries read FROM it.

  ```
  Skill (API/command) → extract + transform → Memex (SQLite) → REST/MCP response
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

  ## Expression Syntax (jaq)

  All dynamic values use jaq expressions (Rust jq). Access `.params.*`, `.auth.*`:

  | Pattern | Expression |
  |---------|-----------|
  | Dynamic URL | `'"https://api.example.com/tasks/" + .params.id'` |
  | Query param | `.params.limit \| tostring` |
  | URL encode | `.params.query \| @uri` |
  | Math / invert | `5 - .params.priority` |
  | Conditional | `'if .params.feed == "new" then "story" else "front_page" end'` |
  | Unix → ISO | `.created_utc \| todate` |
  | Static string | `'"Bearer "'` |
  | Optional field | `.due.date?` |
  | Array wrap | `'[.content]'` |
  | Parse number | `'.ttl \| tonumber'` |
  | String split | `'.auth.key \| split(":") \| .[0]'` |

  In `auth` header values, use `.auth.key` for the credential value.

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
    - skill: write-app
      relationship: appreciates   # Sister skill
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

  This is the attribution layer. See `credits.md` in the core roadmap for the full model.

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
        await aos().call("UseSkill", { skill, tool: "task.list", params: {} });
      } catch (e: any) {
        if (e.message?.includes("Credential not found")) {
          console.log("  ⏭ Skipping: no credentials");
          skipTests = true;
        } else throw e;
      }
    });

    describe("task.list", () => {
      it("returns array of tasks", async () => {
        if (skipTests) return;
        const result = await aos().call("UseSkill", {
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

  **Important:** The validator looks for `tool: "operation.name"` in test files. Include
  every operation, even destructive ones that are skipped.

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

  ## Checklist

  Before submitting a PR:

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

## What Is a Skill?

An AgentOS skill is a YAML-defined adapter that connects an external service — an API,
database, CLI tool, or macOS framework — to the AgentOS entity graph.

Skills live in the community repo (`agentos-community`). The core engine (`agentos`) is
generic and knows nothing about specific services. Everything specific lives here.

When you install a skill, two things happen:
1. **Seed entities** are written to the graph — the service, its org, dependencies, and authors
2. **Operations** become callable via the AgentOS API and MCP, exposing entity data to agents

The entity graph is what makes skills composable. A YouTube video and an iMessage attachment
both become `video` entities. A Todoist task and a Linear issue both become `task` entities.
Same UI. Same queries. Same agent tools. One adapter per source, one experience across all.
