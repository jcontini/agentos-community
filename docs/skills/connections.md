# Connections & Auth

Every skill declares its external service dependencies as **named** `connections:`. Each connection can carry `base_url`, `auth` (with a `type` discriminator), optional `description`, `label`, `help_url`, `optional`, and **local data sources**:

- **`sqlite:`** — path to a SQLite file (tilde-expanded). SQL operations bind to the connection that declares the database; there is **no** top-level `database:` on the skill.
- **`vars:`** — non-secret config (paths, filenames) merged into the executor context (e.g. `params.connection.vars` for Python) so scripts can read local files without hardcoding home-directory paths.

Local skills (no external services) simply omit the `connections:` block.

## Common patterns

Most common — single API key connection:

```yaml
connections:
  api:
    base_url: "https://api.example.com/v1"
    auth:
      type: api_key
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
    auth:
      type: cookies
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

All auth is declared under a single `auth:` key with a `type` discriminator. Three types are supported.

**`api_key`** — API keys/tokens injected via `header`, `query`, or `body` templates with jaq expressions:

```yaml
connections:
  api:
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: API Key
```

**`cookies`** — session cookies resolved from the credential store (for stored sessions) or provider skills (Brave, Firefox):

```yaml
connections:
  web:
    auth:
      type: cookies
      domain: ".claude.ai"
      names: ["sessionKey"]
```

**`oauth`** — OAuth 2.0 token refresh and provider-based acquisition:

```yaml
connections:
  gmail:
    auth:
      type: oauth
      service: google
      scopes:
        - https://mail.google.com/
```

### Resolution algorithm

All auth types follow the same resolution order:

```
1. Check credential store (credentials.sqlite)
2. Check provider skills (find_auth_providers)
3. If optional → skip auth; else → error with help_url
```

This means stored session cookies from `__secrets__` are found before falling back to browser providers.

### Cookie format contract for Python

When a Python function receives `.auth.cookies` (via `args: { cookies: .auth.cookies }` in skill.yaml), the value is a **cookie header string** — e.g. `"name1=val1; name2=val2"`. This is the same format as the HTTP `Cookie` header.

- **`urllib`** — set it directly: `req.add_header("cookie", cookies)` (Chase pattern)
- **`httpx`** — parse to a dict first: `httpx.Client(cookies=parse_cookie_string(cookies))`
- **`requests`** — same as httpx: `requests.get(url, cookies=parse_cookie_string(cookies))`

Helper for parsing:

```python
def _parse_cookie_string(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return {
            k.strip(): v.strip()
            for part in raw.split(";")
            if "=" in part
            for k, _, v in [part.partition("=")]
        }
    return {}
```

Individual cookie values are also available as `.auth.{cookie_name}` — e.g. `.auth.sessionKey` — for operations that need specific cookies by name rather than the full header string.

## Cookie identity resolution

Cookie-auth skills should resolve account identity so the graph knows who the session belongs to. Two deterministic paths exist:

**JSON APIs — use `check.identifier` and `check.display` on the auth block.** The `check` block handles liveness and identity in one HTTP call using jaq expressions on the JSON response:

```yaml
connections:
  web:
    auth:
      type: cookies
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

Skill-level `provides:` is a **typed** list: each entry is either `tool` (capability routing) or `auth` (auth supply).

OAuth provider (excerpt):

```yaml
provides:
  - auth: oauth
    service: google
    via: credential_get
    scopes:
      - https://mail.google.com/
```

Cookie provider (excerpt):

```yaml
provides:
  - auth: cookies
    via: cookie_get
    description: "Cookies from Brave Browser profiles"
```

Consumer skills don't name a specific provider — the runtime discovers installed providers automatically via `find_auth_providers(type, scope)`.

Three cookie providers are available: **Brave** (reads SQLite cookie DB), **Firefox** (reads SQLite cookie DB), and **Playwright** (reads from persistent Chromium session via CDP). Playwright is the primary provider for cookies acquired through login automation flows.

Example references:

- OAuth consumer: `skills/gmail/skill.yaml`
- OAuth provider: `skills/mimestream/skill.yaml`
- Cookie consumer: `skills/claude/skill.yaml`
- Cookie provider (browser DB): `skills/brave-browser/skill.yaml`
- Cookie provider (automation): `skills/playwright/skill.yaml`
- Multi-connection: `skills/goodreads/skill.yaml` (graphql + web)

## Auth failure convention for Python skills

When a Python skill detects an authentication failure from the upstream API (expired session, invalid token, etc.), it should **raise an exception** rather than returning an error dict. The exception message must contain one of: `401`, `403`, `unauthorized`, or `forbidden`. This allows the engine's cookie retry mechanism to detect the failure and retry with fresh cookies from a provider.

```python
# Bad — engine can't detect auth failure, no retry happens
def get_api_keys(cookies: str) -> dict:
    resp = client.get("/api/keys")
    if resp.status_code == 403:
        return {"error": "Session expired"}

# Good — engine detects "403" in the exception, triggers retry
def get_api_keys(cookies: str) -> dict:
    resp = client.get("/api/keys")
    if resp.status_code in (401, 403):
        raise Exception(f"Unauthorized (HTTP {resp.status_code}): session expired")
    data = resp.json()
    if "error" in data and "expired" in data["error"].lower():
        raise Exception("Unauthorized: dashboard session expired")
```

This convention applies to any Python skill that consumes cookie auth (`.auth.cookies`). The engine's retry path invalidates the cookie cache and the credential store skip flag, then re-runs the operation with fresh cookies from a provider.
