# Connections & Auth

Every skill declares its external service dependencies as **named** `connections:`. Each connection can carry `base_url`, auth (`header` / `query` / `body`, `cookies`, `oauth`), optional `description`, `label`, `help_url`, `optional`, and **local data sources**:

- **`sqlite:`** — path to a SQLite file (tilde-expanded). SQL operations bind to the connection that declares the database; there is **no** top-level `database:` on the skill.
- **`vars:`** — non-secret config (paths, filenames) merged into the executor context (e.g. `params.connection.vars` for Python) so scripts can read local files without hardcoding home-directory paths.

Local skills (no external services) simply omit the `connections:` block.

## Common patterns

Most common — single API key connection:

```yaml
connections:
  api:
    base_url: "https://api.example.com/v1"
    header:
      x-api-key: .auth.key
    label: API Key
    help_url: https://example.com/api-keys
```

Multi-connection — public GraphQL + authenticated web session:

```yaml
connections:
  graphql:
    base_url: "https://api.example.com/graphql"
  web:
    cookies:
      domain: ".example.com"
```

Multi-backend — same service, different transports (e.g. SDK + CLI):

```yaml
connections:
  sdk:
    description: "Python SDK — typed models, batch ops, biometric auth"
    vars:
      account_name: "my-account"
  cli:
    description: "CLI tool — stable JSON contract, fallback path"
    vars:
      binary_path: "/opt/homebrew/bin/mytool"
```

When connections differ by transport rather than service, each operation declares which it supports (`connection: [sdk, cli]`). The Python helper receives `connection` as a param and dispatches to the appropriate backend. Both paths normalize output into the same adapter-compatible shape. Use this when: (a) a v0 SDK needs a stable CLI fallback, (b) read ops work with both but writes need the SDK for batch/typed APIs, or (c) offline/online modes with the same data model.

## Rules

- `base_url` on a connection is used to resolve relative `rest.url` and `graphql.endpoint` values
- Single-connection skills auto-infer the connection — no `connection:` needed on each operation
- Multi-connection skills must declare `connection:` on each operation: either one name (`connection: api`) or a **list** (`connection: [api, cache]`) when the caller may choose the backing source (live API vs local cache, etc.)
- With `connection: [a, b, …]`, the first entry is the default; expose `connection` in `params` and pass it through from Python/`rest`/`graphql` so the runtime resolves the effective connection (see `skills/granola/skill.yaml` for `params.connection` wired into `args`)
- Set `connection: none` on operations that should skip auth entirely
- Use `optional: true` if the skill works anonymously but improves with credentials
- Connections without any auth fields (just `base_url`, `sqlite`, `vars`, and/or `description`) are valid — they serve as service declarations

Connection names are arbitrary. Common conventions:

- `api` — REST API with key/token auth
- `graphql` — GraphQL/AppSync (may or may not have auth)
- `web` — cookie-authenticated website (user session)

## Auth types

Three auth resolution mechanisms exist:

**Template auth** (API keys, tokens) — `header`, `query`, or `body` fields with jaq expressions:

```yaml
connections:
  api:
    header:
      Authorization: '"Bearer " + .auth.key'
    label: API Key
```

**Cookie auth** — extracted from installed browsers via provider skills:

```yaml
connections:
  web:
    cookies:
      domain: ".claude.ai"
      names: ["sessionKey"]
```

**OAuth** — token refresh and provider-based acquisition:

```yaml
connections:
  gmail:
    oauth:
      service: google
      scopes:
        - https://mail.google.com/
```

## Cookie identity resolution

Cookie-auth skills should resolve account identity so the graph knows who the session belongs to. Two deterministic paths exist:

**JSON APIs — use `check.identifier` and `check.display` on the connection.** The `check` block handles liveness and identity in one HTTP call using jaq expressions on the JSON response:

```yaml
connections:
  web:
    cookies:
      domain: ".claude.ai"
      names: ["sessionKey"]
      check:
        url: "https://claude.ai/api/organizations"
        expect_status: 200
        identifier: '.[] | select(.capabilities | contains(["chat"])) | .email'
        display: '.[] | select(.capabilities | contains(["chat"])) | .name'
```

**HTML services — use a Python operation with an `account` adapter.** When the introspection endpoint returns HTML (not JSON), identity extraction belongs in Python. The skill declares an `account` adapter and a `check_session` operation that `returns: account`:

```yaml
adapters:
  account:
    id: .customer_id
    name: .display
    issuer: .issuer
    data.marketplace_id: .marketplace_id

operations:
  check_session:
    returns: account
    connection: web
    python:
      module: ./my_skill.py
      function: whoami
      params: true
      timeout: 30
```

The Python function parses the HTML and returns structured identity data including `issuer` (the service domain, e.g. `"amazon.com"`), `customer_id` (a stable account ID used as the adapter `id`), and `display` (a human-friendly name). The extraction pipeline automatically links `account`-tagged nodes to the primary user via `Person --claims--> Account`.

Include `issuer` in the `account` adapter — it's the join key that links the graph entity to credential store rows. The adapter `id` field doubles as the account identifier for dedup.

Leading by example: `skills/amazon/` (HTML identity via Python), `skills/claude/` (JSON identity via `check` block).

## Provider auth

Credentials can come from other installed apps (e.g. Mimestream provides Google OAuth tokens, Brave provides browser cookies).

Skill-level `provides:` is a **typed** list: each entry is either `credentials:` (OAuth or API key), `cookies:`, or `tool:` + `via` for discoverable tools.

OAuth provider (excerpt):

```yaml
provides:
  - credentials:
      oauth:
        service: google
        via: credential_get
        account_param: account
        scopes:
          - https://mail.google.com/
```

Cookie provider (excerpt):

```yaml
provides:
  - cookies:
      via: cookie_get
      account_param: domain
      description: "Short human description for discovery"
```

Consumer skills don't name a specific provider — the runtime discovers installed providers automatically.

Example references:

- OAuth consumer: `skills/gmail/skill.yaml`
- OAuth provider: `skills/mimestream/skill.yaml`
- Cookie consumer: `skills/claude/skill.yaml`
- Cookie provider: `skills/brave-browser/skill.yaml`
- Multi-connection: `skills/goodreads/skill.yaml` (graphql + web)
