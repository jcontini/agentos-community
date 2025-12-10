# Contributing Skills

Thanks for contributing! Here's how to add a new skill.

## Quick Start

1. Fork this repo
2. Create `skills/{service-name}/skill.md` (note: directory + file, not just file)
3. Write your skill with YAML frontmatter + markdown instructions
4. Test your skill locally (see Tips below)
5. Submit a PR

**Note:** The `index.yaml` file is auto-generated from skill frontmatter. You don't need to edit it manually.

## Skill File Structure

Skills use one of two protocols: **shell** (local commands) or **rest/graphql** (cloud APIs).

### Shell Protocol Example

```markdown
---
id: exa
name: Exa
description: Semantic web search and content extraction
category: search
icon: https://cdn.simpleicons.org/exa
color: "#5436DA"
protocol: shell

provides:
  - web-search
  - url-extract

auth:
  type: api_key
  header: x-api-key
  help_url: https://dashboard.exa.ai/api-keys

requires:
  - curl
  - jq

settings:
  num_results:
    label: Number of Results
    description: Default number of search results (1-100)
    type: integer
    default: "5"
    min: 1
    max: 100
  search_type:
    label: Search Type
    description: Default search type
    type: enum
    default: "auto"
    options:
      - auto
      - neural
      - keyword

actions:
  search:
    description: Search the web
    params:
      query:
        type: string
        required: true
        description: Search query
      num_results:
        type: integer
        description: Number of results (overrides setting)
    run: |
      NUM="${PARAM_NUM_RESULTS:-$SETTING_NUM_RESULTS}"
      TYPE="${PARAM_SEARCH_TYPE:-$SETTING_SEARCH_TYPE}"
      curl -s -X POST "https://api.exa.ai/search" \
        -H "x-api-key: $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"$PARAM_QUERY\", \"numResults\": $NUM, \"type\": \"$TYPE\"}"
---

# Exa

Semantic web search and content extraction...
```

### REST Protocol Example

```markdown
---
id: todoist
name: Todoist
description: Personal task management
category: productivity
icon: https://cdn.simpleicons.org/todoist
color: "#E44332"
protocol: rest

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  help_url: https://todoist.com/app/settings/integrations

api:
  type: rest
  base_url: https://api.todoist.com
---

# Todoist

**Use for:** Managing personal tasks, projects, and labels

## Quick Start

List tasks:
```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  https://api.todoist.com/rest/v2/tasks
```

## API Reference

Document the key endpoints and operations...
```

## Protocols

### shell
For skills that execute local commands (CLI tools, scripts, etc.).

**Required fields:**
- `protocol: shell`
- `actions` — Map of action definitions

**Optional fields:**
- `requires` — List of required binaries (e.g., `["yt-dlp", "curl"]`)
- `auth` — Usually `type: local` or `type: api_key` if API key needed

**Action structure:**
```yaml
actions:
  action_name:
    description: What this action does
    params:
      param_name:
        type: string | integer | boolean
        required: true | false
        default: "default value"  # optional
        description: "Parameter description"
    run: |
      # Shell script here
      # Use $PARAM_* for parameters
      # Use $AUTH_TOKEN for credentials (if auth configured)
```

**Environment variables in `run` scripts:**
- `$AUTH_TOKEN` — Credential from agentOS
- `$PARAM_*` — Parameters (uppercased)
- `$AGENTOS_DOWNLOADS` — Downloads folder
- `$AGENTOS_CACHE` — Cache folder

### rest / graphql
For cloud APIs that agentOS proxies.

**Required fields:**
- `protocol: rest` or `protocol: graphql`
- `api` — API configuration
- `auth` — Authentication configuration

**API configuration:**
```yaml
api:
  type: rest     # or graphql
  base_url: https://api.service.com
```

**Permission enforcement:**
- **REST** — GET = See, POST/PUT/PATCH/DELETE = Do
- **GraphQL** — query = See, mutation = Do

## Auth Types

### api_key
Most common. User pastes an API key.

```yaml
auth:
  type: api_key
  header: Authorization    # or X-Api-Key, etc.
  prefix: "Bearer "       # prefix before key (use "" for none)
  help_url: https://...   # where to get the key
```

### oauth
For services using OAuth 2.0.

```yaml
auth:
  type: oauth
  auth_url: https://service.com/oauth/authorize
  token_url: https://service.com/oauth/token
  scopes:
    - read
    - write
  help_url: https://...
```

### service_account
For Google Workspace APIs.

```yaml
auth:
  type: service_account
  scopes:
    - https://www.googleapis.com/auth/gmail.readonly
```

### cli
For CLI tool authentication (e.g., `gh auth login`).

```yaml
auth:
  type: cli
  command: gh
  auth_command: gh auth login
```

### local
For local-only services (no credentials needed).

```yaml
auth:
  type: local
```

## Categories

- `productivity` — Task management, notes, bookmarks
- `communication` — Email, messaging, notifications
- `search` — Web search, content extraction
- `code` — GitHub, GitLab, code hosting
- `finance` — Banking, payments, accounting
- `media` — Video, audio, images

## Index Entry

**Note:** The `index.yaml` file is auto-generated from skill frontmatter. You don't need to manually edit it.

Skills are discovered by scanning `skills/{id}/skill.md` files. The frontmatter contains all metadata needed.

## Complete Skill Schema

### Required Fields

- `id` — Unique identifier (e.g., `"todoist"`, `"youtube"`)
- `name` — Display name (e.g., `"Todoist"`, `"YouTube"`)
- `description` — One-line description
- `category` — One of: `productivity`, `communication`, `search`, `code`, `finance`, `media`
- `protocol` — `rest`, `graphql`, or `shell` (default: `rest`)

### Optional Display Fields

- `icon` — Icon URL (e.g., `"https://cdn.simpleicons.org/todoist"`)
- `color` — Brand color hex (e.g., `"#E44332"`)

### Optional Capability Fields

- `provides` — List of capabilities this skill provides (e.g., `["web-search", "url-extract"]`)
  - Available capabilities: `web-search`, `url-extract`
  - Used by agentOS to route capability requests to appropriate skills
- `settings` — User-configurable settings that appear in the UI (see Settings Schema below)

### Protocol-Specific Fields

**For `shell` protocol:**
- `requires` — List of required binaries (e.g., `["yt-dlp", "curl"]`)
- `actions` — Map of action definitions (see Shell Actions below)
- `auth` — Usually `type: local` (no credentials) or `type: api_key` if API key needed

**For `rest`/`graphql` protocol:**
- `api` — API configuration with `type` and `base_url`
- `auth` — Authentication configuration (see Auth Types below)

### Shell Actions

Each action has:
- `description` — What the action does
- `params` — Parameter definitions (optional)
- `run` — Shell script to execute

**Parameter schema:**
```yaml
params:
  param_name:
    type: string | integer | boolean
    required: true | false
    default: "default value"  # optional
    description: "What this parameter does"
```

**Environment variables available in `run` scripts:**
- `$AUTH_TOKEN` — Credential from agentOS (if auth configured)
- `$PARAM_*` — Parameters (uppercased, e.g., `$PARAM_URL`, `$PARAM_LANG`)
- `$SETTING_*` — User settings (uppercased, e.g., `$SETTING_NUM_RESULTS`)
- `$AGENTOS_DOWNLOADS` — Downloads folder path
- `$AGENTOS_CACHE` — Cache folder path

### Settings Schema

Skills can expose user-configurable settings that appear in the agentOS preferences UI. Settings are passed to action scripts as `$SETTING_*` environment variables.

**Example:**
```yaml
settings:
  num_results:
    label: Number of Results
    description: Default number of search results to return (1-100)
    type: integer
    default: "5"
    min: 1
    max: 100
  search_type:
    label: Search Type
    description: Default search type
    type: enum
    default: "auto"
    options:
      - auto
      - neural
      - keyword
  include_text:
    label: Include Text Content
    description: Include page text content by default
    type: boolean
    default: "false"
```

**Setting types:**
- `integer` — Number input with optional `min`/`max` validation
- `enum` — Dropdown with predefined `options` array
- `boolean` — Toggle switch (values: `"true"` or `"false"` as strings)
- `string` — Text input

**Required fields:**
- `label` — Display name in UI
- `description` — Help text
- `type` — One of: `integer`, `enum`, `boolean`, `string`
- `default` — Default value (always as string, even for numbers/booleans)

**Optional fields:**
- `min`, `max` — For `integer` type
- `options` — For `enum` type (array of strings)

**Usage in actions:**
Settings are available as `$SETTING_*` environment variables (uppercased):
```bash
NUM="${PARAM_NUM_RESULTS:-$SETTING_NUM_RESULTS}"  # Use param or fall back to setting
```

## Tips

1. **Look at examples** — See `skills/exa/skill.md` and `skills/youtube/skill.md` for shell protocol examples
2. **Test actions first** — For shell skills, test the `run` scripts manually with sample parameters
3. **Keep it concise** — AI reads this, so less is often more
4. **Show real examples** — Actual commands/API calls that work
5. **Note quirks** — API gotchas, rate limits, pagination, edge cases
6. **Use environment variables** — `$PARAM_*` for parameters, `$AUTH_TOKEN` for credentials
7. **Test locally** — Set `skills_source` in agentOS settings to your local repo path to test changes

## Questions?

Open an issue or discussion!
