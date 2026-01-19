# Contributing to AgentOS Community

This repo contains plugins, components, apps, and agent configs — all declarative YAML.

| Content Type | What It Is |
|--------------|------------|
| **Plugins** | Service integrations (APIs, databases, local apps) |
| **Components** | Reusable UI building blocks |
| **Apps** | Capability renderers that compose components |
| **Agents** | Setup instructions for AI clients |

---

## Plugins

Plugins connect AgentOS to external services. Each plugin is a YAML config that describes how to talk to an API — AgentOS handles auth, execution, and response mapping automatically.

## Creating a Plugin

```bash
npm run new-plugin myservice           # API with full CRUD
npm run new-plugin myservice --readonly # API, read-only
npm run new-plugin myservice --local    # Local (no auth needed)
```

This generates everything you need: config, icon, and tests. Edit the generated `readme.md` with your API details and you're done.

## How It Works

A plugin is just a `readme.md` with YAML frontmatter:

```yaml
---
id: myservice
name: My Service
description: What it does
auth:
  type: api_key
  header: Authorization

actions:
  list:
    operation: read
    rest:
      method: GET
      url: https://api.example.com/items
      response:
        mapping:
          id: "[].id"
          title: "[].name"
---

# My Service

Setup instructions and documentation here.
```

**Key concepts:**

- **`operation`** — Every action declares what it does: `read`, `create`, `update`, or `delete`. This powers our security features and test requirements.

- **`auth`** — Declare the auth type and AgentOS injects credentials automatically. Never put secrets in configs.

- **Response mapping** — Transform API responses into a standard format. The `[].field` syntax maps arrays, `.field` maps single objects.

## Testing

Tests are auto-generated and validated by our linter. The system:

1. **Infers requirements from your config** — If your plugin has `auth`, tests must handle missing credentials gracefully. If it has `create` operations, tests must clean up test data.

2. **Enforces standards automatically** — The pre-commit hook runs the linter. If something's missing, it tells you what to add.

3. **Supports exemptions** — Edge cases can opt out with a documented reason in the YAML.

```bash
npm run lint:tests           # Check your tests
npm test plugins/myservice   # Run your tests
```

## Commands

```bash
npm run new-plugin <name>    # Create a new plugin
npm run lint:tests           # Validate test patterns
npm run validate             # Validate plugin schemas
npm test                     # Run all tests
```

## Git Hooks

Everything is validated before you can commit:

- **Schema validation** — Catches malformed YAML
- **Security checks** — Blocks credential exposure
- **Test linting** — Ensures tests follow standards

If the hook fails, it tells you exactly what to fix.

## Executors

Plugins support multiple backends:

| Executor | Use Case |
|----------|----------|
| `rest:` | REST APIs |
| `graphql:` | GraphQL APIs |
| `sql:` | Local databases |
| `swift:` | macOS native APIs |
| `command:` | Shell commands |

See existing plugins for examples: `linear` (GraphQL), `exa` (REST), `imessage` (SQL), `apple-contacts` (Swift).

## Philosophy

**We enforce, not instruct.** The scaffold generates correct code. The linter catches mistakes. The hooks block bad commits. You focus on the API integration — we handle the standards.

**Real credentials, real APIs.** Tests call actual APIs with your production credentials. No mocking. This catches real bugs.

**Graceful degradation.** Tests skip if credentials aren't configured. Contributors without API keys can still run the test suite.

**Clean up after yourself.** If tests create data, they delete it. The linter enforces this for any plugin with `create` operations.

---

## Components

Components are reusable UI pieces. They compose atoms (text, image, icon, container) or other components.

**Location:** `components/{component-id}/readme.md`

```yaml
---
id: search-result
name: Search Result
description: A search result card

props:
  title: string
  url: string
  snippet: string?

root:
  type: container
  direction: column
  children:
    - type: text
      value: "{{props.title}}"
      style: bold
    # ...
---

# Search Result

Documentation here.
```

See `components/url-bar/` and `components/search-result/` for examples.

---

## Apps

Apps render capabilities. They define how plugin responses are displayed.

**Location:** `apps/{app-id}/readme.md`

```yaml
---
id: browser
name: Browser
capabilities: [web_search, web_read]

views:
  search:
    when: "capability == 'web_search'"
    root:
      type: container
      children:
        - component: url-bar
          value: "{{request.query}}"
        # ...
---

# Browser

Documentation here.
```

See `apps/browser/` for an example.

---

## Agents

Agents are setup instructions for AI clients. Documentation only — not executable.

**Location:** `agents/{agent-id}/readme.md`

```yaml
---
id: cursor
name: Cursor
description: AI-powered code editor
---

# Cursor Setup

Setup instructions here.
```

See `agents/cursor/` for an example.

---

## Reference

| Resource | Purpose |
|----------|---------|
| `tests/plugin.schema.json` | Schema for valid plugin configs |
| `plugins/linear/` | GraphQL plugin example |
| `plugins/exa/` | REST plugin example |
| `plugins/goodreads/` | Local file plugin example |
| `components/url-bar/` | Component example |
| `apps/browser/` | App example |
| `agents/cursor/` | Agent example |

---

## License & Contributions

This repository is **MIT licensed** — you can use, modify, and redistribute freely.

**By contributing, you agree that:**

1. Your contribution is MIT licensed and will remain open source
2. A Third Party, LLC (the company behind AgentOS) may use your contribution in official releases, including commercial offerings
3. You have the right to make this contribution

**What you get:**

- Your code stays open forever under MIT
- Credit in commit history

We're exploring ways to share revenue with contributors in the future, but this is not a commitment or guarantee.
