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

**`cookies`** — session cookies resolved from the credential store (for stored sessions) or provider skills (Brave, Firefox, Playwright):

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

Cookie auth uses **timestamp-based resolution** — all sources are checked, and the one with the newest cookies wins. There is no fixed priority order and no TTL-based expiry.

#### Sources

Three sources of cookies exist, each with different freshness characteristics:

| Source | What it is | Freshness |
|--------|-----------|-----------|
| **In-memory cache** | Cookies from the last extraction, updated by `Set-Cookie` responses from our own HTTP requests (writeback). Lives in engine process memory. | Can be *newer* than the browser — when a server rotates a session token via `Set-Cookie` in response to our request, the cache has the new value before the browser does. |
| **Browser providers** (Brave, Firefox) | Fresh extraction from the browser's local cookie database. | Reflects the user's latest browsing — if they just visited Amazon and got a fresh session, the browser has the newest cookies. |
| **Credential store** (`credentials.sqlite`) | Persistent copy of cookies, also updated by writeback. Survives engine restart. | Same data as the cache, but persistent. Staler than the cache if writeback updated the cache since last store write. |

#### How it works

```
1. Gather candidates from ALL sources:
   a. In-memory cache           (instant — HashMap lookup)
   b. Browser providers          (~20ms — local SQLite reads)
   c. Credential store           (~1ms — local SQLite read)

2. Score each candidate:
   - Filter expired cookies
   - Build cookie header string
   - Compute newest_cookie_at (latest per-cookie timestamp)

3. Pick the candidate with the highest newest_cookie_at.
   On ties, the first candidate (cache) wins.

4. If winner is from cache → return immediately (identity already known)
   If winner is from a provider → run account_check for identity, persist to store + cache
   If winner is from store → return as-is (fallback)

5. If no candidates → error with help_url
6. On SESSION_EXPIRED or 401/403 → exclude failed provider, retry
```

#### Per-cookie timestamps

Every cookie carries a timestamp tracking when it was last set:

- **Browser cookies** have a `created` field (Unix seconds with sub-second precision) from the browser's cookie database. Brave and Firefox both provide this.
- **Writeback cookies** (from `Set-Cookie` responses to our HTTP requests) get stamped with `now()` when the engine processes the response. This is how our cache becomes *newer* than the browser after a server-side token rotation.
- **Store cookies** carry a `cookie_timestamps` map in the value blob, updated on writeback via `merge_cookie_header`.

The `newest_cookie_at` for a candidate is the maximum timestamp across all its cookies. This single number determines who wins.

#### Example: why timestamps matter

```
Call 1 (cold start — no cache):
  Cache:    empty
  Brave:    session_token created at 1712019700.5    ← winner (only candidate)
  Store:    empty
  → Extracts from Brave, runs account_check, persists to store + cache

Call 2 (cache populated):
  Cache:    session_token at 1712019700.5
  Brave:    session_token at 1712019700.5             (same — user hasn't browsed)
  Store:    session_token at 1712019700.5
  → Tie — cache wins (first candidate). No account_check needed. ~58ms.

Call 3 (server rotated token via Set-Cookie):
  Cache:    session_token at 1712019800.0              ← winner (writeback stamped now())
  Brave:    session_token at 1712019700.5
  Store:    session_token at 1712019800.0
  → Cache wins. The server gave US the new token; the browser doesn't have it yet.

Call 4 (user browsed Amazon, got fresh cookies):
  Cache:    session_token at 1712019800.0
  Brave:    session_token at 1712019900.3              ← winner (user's browsing is newest)
  Store:    session_token at 1712019800.0
  → Brave wins. Fresh extraction, account_check runs, cache + store updated.
```

#### Why no TTL?

Previous versions used a 5-minute TTL on the cache — entries older than 5 minutes were treated as stale. This was arbitrary and wrong in both directions: too aggressive when writeback kept the cache genuinely fresh, too lenient when the browser got new cookies 30 seconds later.

Timestamps replace TTL entirely. A cache entry from 10 minutes ago still wins if its cookies are genuinely newer than what the browser has. A cache entry from 1 second ago loses if the browser has fresher cookies. The timestamp is the only arbiter.

#### Playwright

Playwright (live browser session via CDP) is **always skipped** unless explicitly requested via the `provider` parameter. It launches a visible Chrome window — too expensive and disruptive for automatic resolution. Use it for reverse engineering and login flows, not for runtime auth.

### Cookie format contract for Python

When a Python function receives `.auth.cookies` (via `args: { cookies: .auth.cookies }` in skill.yaml), the value is a **cookie header string** — e.g. `"name1=val1; name2=val2"`. This is the same format as the HTTP `Cookie` header.

Pass it directly to `agentos.http`:

```python
from agentos import http

# Simple request
resp = http.get(url, cookies=cookie_header, **http.headers(accept="json"))

# Session with cookie jar
with http.client(cookies=cookie_header) as c:
    resp = c.get(url, **http.headers(waf="cf", accept="html"))
```

The SDK helpers `get_cookies(params)` and `require_cookies(params, op)` extract the cookie header from `params.auth.cookies`:

```python
from agentos.http import require_cookies

cookie_header = require_cookies(params, "list_orders")
# Raises ValueError if no cookies available
```

Individual cookie values are also available as `.auth.{cookie_name}` — e.g. `.auth.sessionKey` — for operations that need specific cookies by name rather than the full header string.

### Cookie domain filtering (RFC 6265)

The engine automatically filters cookies by RFC 6265 domain matching when resolving auth. If a connection declares `base_url: "https://riders.uber.com"`, only cookies whose domain matches `riders.uber.com` (including parent domains like `.uber.com`) are included. Sibling subdomain cookies (`.auth.uber.com`, `.www.uber.com`) are filtered out. Skills don't need to handle this — the provider does it automatically.

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

When a Python skill detects an authentication failure, it should **raise an exception** rather than returning an error dict. Two conventions exist, and the engine handles both:

### Convention 1: `SESSION_EXPIRED:` prefix (preferred for cookie-auth skills)

Use `SESSION_EXPIRED:` when the skill can definitively detect that the session is stale — typically via login redirects, expired-session pages, or specific error responses. This is the **recommended convention** for cookie-authenticated skills.

```python
def list_orders(params):
    cookie_header = _require_cookies(params, "list_orders")
    with _auth_client(cookie_header) as client:
        resp = client.get(f"{BASE}/your-orders/orders")
        body = resp.text

    if _is_login_redirect(resp, body):
        raise RuntimeError(
            "SESSION_EXPIRED: Amazon redirected to login — session cookies are expired or invalid."
        )
    return _parse_orders(body)
```

**Format:** `SESSION_EXPIRED: <human-readable reason>`

The engine catches this prefix, excludes the current cookie provider from the candidate list, and retries with the next-best provider. This handles the common case where one browser has stale cookies but another (e.g. Playwright with a live session) has fresh ones.

### Convention 2: HTTP status codes in exception message (fallback)

For API-style endpoints that return standard HTTP status codes, include `401`, `403`, `unauthorized`, or `forbidden` in the exception message:

```python
def get_api_keys(cookies: str) -> dict:
    resp = client.get("/api/keys")
    if resp.status_code in (401, 403):
        raise Exception(f"Unauthorized (HTTP {resp.status_code}): session expired")
```

Both conventions trigger the same retry behavior: invalidate the cookie cache, exclude the failing provider, and re-run with fresh cookies.

### When to use which

| Situation | Convention |
|---|---|
| HTML scraping — login redirect detected | `SESSION_EXPIRED:` prefix |
| HTML scraping — auth wall / sign-in page | `SESSION_EXPIRED:` prefix |
| JSON API returns 401/403 | HTTP status in exception |
| Dashboard returns error JSON with "expired" | Either — `SESSION_EXPIRED:` is clearer |

### Provider retry behavior

The engine retries **once** on auth failure, with the failing provider excluded:

```
1. Engine selects best provider (e.g. Brave, 23 cookies)
2. Skill runs, raises SESSION_EXPIRED
3. Engine excludes Brave, re-selects (e.g. Playwright, 16 cookies)
4. Skill runs again with Playwright's cookies
5. If this also fails → error surfaces to the caller (no infinite loops)
```

## Cookie provider selection

When multiple browser cookie providers are installed (Brave, Firefox), they all
run as candidates alongside the cache and store. The winner is determined by
`newest_cookie_at` — the latest per-cookie timestamp across all cookies.

Within the provider tier (when comparing two browser providers against each other),
the scoring heuristic breaks ties:

1. **Required cookie names** — providers that have all cookies listed in the
   connection's `names` field score highest
2. **Creation timestamp** — the provider whose cookies were created most recently
   wins
3. **Cookie count** — final tiebreaker when all else is equal

Playwright is always skipped unless explicitly requested (see above).

### Explicit provider override

When the automatic selection picks wrong (or for testing), pass `provider` as a
top-level argument to `run()`:

```
run({ skill: "amazon", tool: "list_orders", provider: "playwright" })
```

This bypasses the selection heuristic entirely and uses the specified provider.
Valid provider names are the skill IDs of installed cookie providers (e.g.
`"playwright"`, `"brave-browser"`, `"firefox"`).
