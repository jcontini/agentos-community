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

  ### Choosing the right entity type

  Always map to an existing entity before creating a new one. Existing entity types:
  `task`, `person`, `message`, `conversation`, `post`, `video`, `channel`, `document`,
  `meeting`, `forum`, `webpage`, `tag`

  Check `entities/{type}.yaml` in the community repo for exact property names.

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
  | `operation_result` | Actions that succeed or fail (`{ success, message?, id? }`) |
  | `batch_result` | Bulk operations (`{ succeeded, failed, total, errors? }`) |
  | `void` | No useful return value |

  ### Executors

  | Executor | Use case |
  |----------|----------|
  | `rest` | HTTP REST APIs |
  | `graphql` | GraphQL APIs |
  | `sql` | SQLite databases |
  | `command` | Shell commands / CLI tools |
  | `swift` | macOS native frameworks (EventKit, Contacts, etc.) |

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

  For operations that don't fit standard entity CRUD — custom return shapes, introspection,
  bulk actions:

  ```yaml
  utilities:
    get_workflow_states:
      description: List available workflow states
      rest:
        method: GET
        url: https://api.myservice.com/states
      returns:
        type: array
        items:
          id: .id
          name: .name
  ```

  Utility names are `verb_noun` (no dot). They appear in the API alongside operations.

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
  - [ ] All required front matter: `id`, `name`, `description`, `icon`
  - [ ] Auth configured correctly for the service
  - [ ] `transformers` map to existing entity types (checked `entities/*.yaml`)
  - [ ] Operations use correct `entity.operation` naming
  - [ ] Seed entities credit the upstream service + any CLI/library dependencies
  - [ ] Tests cover all operations (even skipped destructive ones)
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
