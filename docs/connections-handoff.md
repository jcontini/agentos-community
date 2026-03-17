# Handoff: `connections:` Architecture for Multi-Auth Skills

## The Problem

Today a skill has one `auth:` block. This works for simple skills (Exa, Todoist, Linear) but breaks down for skills that talk to a service through multiple auth contexts.

Goodreads is the motivating case. It has:

- **Public GraphQL operations** — use an AppSync API key that's auto-discovered from JS bundles. No user credentials needed, but the system still had to discover the key. This IS credential resolution — it's just automated.
- **Authenticated web operations** — use the user's Goodreads session cookies for viewer-scoped data (shelves, reading status, social features).

Today this is hacked with a single `auth: { cookies: ..., optional: true }` block and per-operation `auth: none` overrides on every public operation. It works but it's a workaround, not a model.

The same pattern applies to Austin Boulder Project (public schedule + authenticated bookings), and will apply to any skill where some operations are public and others need user auth.

## The Design

### New top-level key: `connections:`

A named map of auth contexts. Each connection has a name, optional description, and an auth configuration (same types as today: cookies, header, body, query, oauth, or nothing).

### Operations reference connections via `connection:`

Instead of `auth: none` or relying on the skill-level default, each operation says which connection it uses.

### `auth:` stays for simple skills

Skills with a single auth method keep using `auth:` unchanged. No migration needed. `connections:` and `auth:` are mutually exclusive — the runtime detects which model a skill uses.

### Concrete example: Goodreads

```yaml
id: goodreads
name: Goodreads
description: Book discovery, reviews, and reading lists from Goodreads
icon: icon.svg
website: https://www.goodreads.com

connections:
  graphql:
    description: "Public AppSync GraphQL — API key auto-discovered from JS bundles"

  web:
    description: "Goodreads user cookies for viewer-scoped data"
    cookies:
      domain: ".goodreads.com"
      names: ["session_id", "__Secure-user_session"]
    label: Goodreads Session
    help_url: https://www.goodreads.com/user/sign_in

operations:
  search_books:
    description: Search books by title or author
    connection: graphql
    returns: book[]
    python:
      module: ./public_graph.py
      function: search_books
      args:
        query: .params.query
        limit: '.params.limit // 10'

  list_book_reviews:
    description: List reviews for a book
    connection: graphql
    returns: review[]
    python:
      module: ./public_graph.py
      function: list_book_reviews
      args:
        book_id: .params.book_id
        limit: '.params.limit // 30'

  get_user_shelves:
    description: List a user's bookshelves
    connection: web
    returns: shelf[]
    python:
      module: ./public_graph.py
      function: get_user_shelves
      args:
        user_id: .params.user_id
```

### Concrete example: Exa (unchanged)

```yaml
id: exa
name: Exa
auth:
  header:
    x-api-key: .auth.key
  label: API Key
  help_url: https://dashboard.exa.ai/api-keys

operations:
  search:
    description: Search the web
    returns: result[]
    rest:
      method: POST
      url: https://api.exa.ai/search
      body:
        query: .params.query
```

No `connections:`, no `connection:` on operations. Completely unchanged.

### Concrete example: Austin Boulder Project (multi-connection)

```yaml
id: austin-boulder-project
name: Austin Boulder Project

connections:
  api:
    description: "Public schedule and facility data"

  account:
    description: "Authenticated account access for bookings and memberships"
    header:
      Authorization: .auth.key
    label: "ABP credentials — enter as email:password"
    help_url: https://boulderingproject.portal.approach.app/login

operations:
  get_schedule:
    connection: api
    returns: class[]
    python:
      module: ./abp.py
      function: get_schedule
      args:
        date: .params.date

  book_class:
    connection: account
    returns: booking
    python:
      module: ./abp.py
      function: book_class
      args:
        class_id: .params.class_id
```

## V1 Scope: What to Build

V1 is `connections:` with per-connection auth resolution. It uses the same auth mechanisms that exist today (cookies, header, body, query, oauth), just scoped to named connections instead of a single skill-level block.

### What V1 does

- Parse `connections:` from skill YAML — a named `IndexMap<String, Connection>`.
- Each `Connection` has the same auth fields as today's `SkillAuth`: `cookies`, `header`, `query`, `body`, `oauth`, `label`, `help_url`, plus an optional `description`.
- When executing an operation with `connection: <name>`, look up that connection's auth config and use it for auth resolution.
- If the connection has `cookies:`, do cookie provider matchmaking (same mechanism, same `provides: [{ service: "cookies" }]` on provider skills).
- If the connection has `header:`/`body:`/`query:`, do credential resolution (same mechanism as today's `SkillAuth`).
- If the connection has `oauth:`, do OAuth resolution (same mechanism).
- If the connection has no auth fields, skip auth. The executor handles everything (e.g., the Python module discovers its own API key).
- `auth:` on the skill level = old path, completely unchanged.
- `connections:` and `auth:` are mutually exclusive on a given skill.

### What V1 does NOT do

- No `discover:` block for automated credential resolution. That's v2.
- No runtime-injected values into operations from connections.
- No changes to executors. They stay dumb — they execute, they don't resolve auth.
- No changes to provider skills. They keep declaring `provides:` the same way.

### What V2 adds later

V2 introduces `discover:` — a block on a connection that tells the runtime to call a Python (or other) module to auto-discover credentials. The module returns structured values (endpoint, API key, etc.) that the runtime caches and makes available to operations.

This is documented here for context but is NOT part of v1:

```yaml
connections:
  graphql:
    description: "Public AppSync GraphQL"
    discover:
      module: ./public_graph.py
      function: discover_runtime
    # Runtime calls discover_runtime(), caches result,
    # and makes discovered values available to operations.
    # The exact injection mechanism (how operations consume
    # discovered values) is a v2 design decision.
```

In v1, the `graphql` connection has no auth fields, so the runtime does nothing for auth. The Python module calls `discover_runtime()` internally, as it does today. This works. V2 just elevates that pattern to the runtime level.

## Key Principles

1. **Matchmaking, not references.** Skills declare what they need (`cookies: { domain: ".goodreads.com" }`) or what they provide (`provides: [{ service: "cookies" }]`). Skills never reference other skills by name.

2. **Implicit over explicit.** If a connection has no auth fields, the runtime infers "no auth needed" — no `tier: public` or `auth: none` declaration required. The connection's nature is determined by what it contains.

3. **Executors stay dumb.** Auth resolution happens at the runtime level before the executor runs. The executor receives params with auth already injected (`.auth.cookies`, `.auth.key`, etc.) and just executes. No executor changes needed for v1.

4. **Backwards compatible.** `auth:` keeps working. Simple skills don't change. The runtime detects `connections:` vs `auth:` and uses the appropriate path.

## Rust Implementation Plan

All paths relative to `/Users/joe/dev/agentos`.

### 1. `crates/core/src/skills/types.rs` — Add the structs

#### Add `Connection` struct

The `Connection` struct reuses the same fields as `SkillAuth`, plus a description. It represents one named auth context:

```rust
/// A named auth context within a multi-connection skill.
///
/// Each connection declares how to authenticate for a subset of operations.
/// The auth fields (cookies, header, query, body, oauth) are the same as
/// SkillAuth — a Connection is essentially a named SkillAuth with a description.
///
/// ```yaml
/// connections:
///   web:
///     description: "User session cookies"
///     cookies:
///       domain: ".goodreads.com"
///       names: ["session_id"]
///     label: Goodreads Session
///   graphql:
///     description: "Public API — no user auth needed"
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Connection {
    #[serde(default)]
    pub description: Option<String>,

    #[serde(default)]
    pub header: Option<HashMap<String, String>>,
    #[serde(default)]
    pub query: Option<HashMap<String, String>>,
    #[serde(default)]
    pub body: Option<HashMap<String, String>>,
    #[serde(default)]
    pub cookies: Option<CookieAuth>,
    #[serde(default)]
    pub oauth: Option<OAuthConfig>,

    #[serde(default)]
    pub label: Option<String>,
    #[serde(default)]
    pub help_url: Option<String>,
}
```

Consider factoring out the shared auth fields into a trait or helper, since `Connection` and `SkillAuth` have the same cookie/header/query/body/oauth fields. But for v1, simple duplication is fine — refactor later if it bothers you.

Add a helper to convert a `Connection` to a `SkillAuth` (or extract the auth-relevant parts) so the existing resolution functions can be reused:

```rust
impl Connection {
    /// Convert to a SkillAuth for reuse in existing auth resolution functions.
    pub fn as_skill_auth(&self) -> SkillAuth {
        SkillAuth {
            header: self.header.clone(),
            query: self.query.clone(),
            body: self.body.clone(),
            cookies: self.cookies.clone(),
            oauth: self.oauth.clone(),
            label: self.label.clone(),
            help_url: self.help_url.clone(),
            optional: None,
            // ... other SkillAuth fields as None/default
        }
    }

    pub fn has_auth(&self) -> bool {
        self.header.is_some()
            || self.query.is_some()
            || self.body.is_some()
            || self.cookies.is_some()
            || self.oauth.is_some()
    }
}
```

#### Add `connections` to `Skill`

```rust
pub struct Skill {
    // ... existing fields ...

    /// Named auth contexts for multi-connection skills.
    /// Mutually exclusive with `auth:` — a skill uses one model or the other.
    /// Operations reference connections by name via `connection: <name>`.
    #[serde(default)]
    pub connections: IndexMap<String, Connection>,

    // ... rest of existing fields ...
}
```

#### Add `connection` to `Operation`

The `Operation` struct at line 326 already has `pub auth: Option<String>` (line 380). Add `connection` alongside it:

```rust
pub struct Operation {
    // ... existing fields ...

    /// Per-operation auth override (old model). Set to "none" to skip.
    #[serde(default)]
    pub auth: Option<String>,

    /// Named connection reference (new model). Points to a key in skill.connections.
    #[serde(default)]
    pub connection: Option<String>,

    // ... executors ...
}
```

### 2. `crates/core/src/skills/executor.rs` — Wire connection-based auth resolution

The two main dispatch points are:

- `extract_operation_inner` (line 150) — entity-returning operations
- `execute_operation_inner` (line 235) — inline-schema operations

Both currently do:

```rust
let params = inject_auth_into_params(skill, &wrapped_params, account)?;
let auth_override = operation.auth.as_deref();
```

#### Add connection resolution

Before the executor dispatch, add connection-based auth resolution:

```rust
fn extract_operation_inner(
    skill: &Skill,
    operation: &Operation,
    params: &Value,
    account: Option<&str>,
) -> Result<ExtractResult, String> {
    let raw_params = apply_param_defaults(operation.params.as_ref(), params);
    let wrapped_params = wrap_params(&raw_params);

    // Resolve auth: connection model vs legacy auth model
    let (params, auth_override) = if !skill.connections.is_empty() {
        // New model: look up the named connection
        resolve_connection_auth(skill, operation, &wrapped_params, account)?
    } else {
        // Legacy model: skill-level auth + per-operation override
        let params = inject_auth_into_params(skill, &wrapped_params, account)?;
        let auth_override = operation.auth.as_deref().map(String::from);
        (params, auth_override)
    };
    let auth_override_ref = auth_override.as_deref();

    // ... existing executor dispatch unchanged ...
}
```

#### Implement `resolve_connection_auth`

```rust
fn resolve_connection_auth(
    skill: &Skill,
    operation: &Operation,
    params: &Value,
    account: Option<&str>,
) -> Result<(Value, Option<String>), String> {
    let Some(ref conn_name) = operation.connection else {
        // Operation doesn't specify a connection in a connections-model skill.
        // No auth resolution — skip.
        return Ok((params.clone(), Some("none".to_string())));
    };

    let Some(connection) = skill.connections.get(conn_name) else {
        return Err(format!(
            "Operation references connection '{}' but skill '{}' has no such connection. Available: {:?}",
            conn_name, skill.id, skill.connections.keys().collect::<Vec<_>>()
        ));
    };

    if !connection.has_auth() {
        // Connection has no auth fields — no resolution needed.
        return Ok((params.clone(), Some("none".to_string())));
    }

    // Convert connection to SkillAuth and reuse existing resolution.
    // Build a temporary skill-like context for the auth functions.
    let temp_auth = connection.as_skill_auth();

    // For cookie auth:
    if let Some(ref cookie_auth) = temp_auth.cookies {
        let preferred_provider = preferred_cookie_provider(params);
        match resolve_cookie_auth_cached(cookie_auth, preferred_provider.as_deref()) {
            Ok(injection) => {
                // Inject cookies into params (same as inject_auth_into_params)
                let params = inject_cookie_into_params(params, &injection, cookie_auth, preferred_provider.as_deref())?;
                return Ok((params, None));
            }
            Err(err) => return Err(err),
        }
    }

    // For header/query/body template auth:
    if temp_auth.has_templates() {
        let credential = resolve_credential(&skill.id, account)?;
        let params = inject_credential_into_params(params, &credential)?;
        return Ok((params, None));
    }

    // For OAuth:
    if temp_auth.oauth.is_some() {
        // Reuse existing OAuth resolution — this injects into adapter auth, not params.
        // For the command/python executor path, we need params injection.
        // This may need the same handling as inject_auth_into_params.
        return Ok((params.clone(), None));
    }

    Ok((params.clone(), Some("none".to_string())))
}
```

Note: The exact implementation depends on how cleanly the existing `inject_auth_into_params` and `inject_adapter_auth` functions can be reused. The key insight is that a `Connection` is just a named `SkillAuth`, so the same resolution functions apply — you're just looking up the auth config from `skill.connections[name]` instead of `skill.auth`.

#### Cookie retry on 401/403

The `execute_operation_inline` function (line 202) currently retries on 401/403 by checking `skill.auth.cookies`. For connection-model skills, it needs to look up the operation's connection instead:

```rust
pub fn execute_operation_inline(
    skill: &Skill,
    operation: &Operation,
    params: &Value,
    account: Option<&str>,
) -> Result<ExecutionOutput, String> {
    let result = execute_operation_inner(skill, operation, params, account);

    if result.is_err() {
        // Find the cookie domain to invalidate: from connection or legacy auth
        let cookie_domain = if !skill.connections.is_empty() {
            operation.connection.as_ref()
                .and_then(|name| skill.connections.get(name))
                .and_then(|conn| conn.cookies.as_ref())
                .map(|c| c.domain.clone())
        } else {
            skill.auth.as_ref()
                .and_then(|a| a.cookies.as_ref())
                .map(|c| c.domain.clone())
        };

        if let Some(domain) = cookie_domain {
            let err_msg = result.as_ref().unwrap_err();
            let err_lower = err_msg.to_lowercase();
            if err_lower.contains("401") || err_lower.contains("403")
                || err_lower.contains("unauthorized") || err_lower.contains("forbidden")
            {
                invalidate_cookie_cache(&domain);
                return execute_operation_inner(skill, operation, params, account);
            }
        }
    }

    result
}
```

#### `inject_adapter_auth` for REST/GraphQL executors

The `inject_adapter_auth` function (line 2103) currently reads from `skill.auth`. For connection-model skills, it needs to read from the operation's connection. The simplest approach:

```rust
fn inject_adapter_auth(
    skill: &Skill,
    params: &Value,
    account: Option<&str>,
    auth_override: Option<&str>,
) -> Result<AuthInjection, String> {
    if auth_override == Some("none") {
        return Ok(AuthInjection::empty());
    }

    // ... existing code reads from skill.auth ...
    // This function doesn't know the operation, so the caller (extract_rest, etc.)
    // needs to pass the resolved auth config. See below.
}
```

There are two approaches:

**Approach A (simpler):** The dispatch code in `extract_operation_inner` already handles connection resolution before calling executors. For the command/python path, auth is injected into params. For the REST/GraphQL path, the `auth_override` mechanism already works — if the connection has no auth, pass `auth_override = Some("none")`. If it has auth, the params already have `.auth.*` injected.

**Approach B (cleaner):** Pass the resolved `SkillAuth` (from the connection or from `skill.auth`) into `inject_adapter_auth` instead of having it read `skill.auth` directly. This is a larger refactor but cleaner long-term.

For v1, Approach A is recommended. The connection resolution happens early in `extract_operation_inner` / `execute_operation_inner`, and the existing executor functions don't need to change.

### 3. `crates/core/src/skills/loader.rs` — No changes needed

Serde will deserialize `connections:` automatically once the struct fields exist. The loader parses YAML front matter into a `Skill` struct with `serde_yaml::from_str(yaml)` (line ~35). No custom parsing needed.

### 4. Validation

The validator (`validate` command, `test-skills.cjs`) should check:

- If a skill has `connections:`, every operation MUST have `connection:` (or it's an error).
- If a skill has `auth:` (old model), operations should NOT have `connection:`.
- A skill cannot have both `connections:` and `auth:` (mutually exclusive).
- Each `connection:` value on an operation must match a key in `connections:`.

These checks should be added to the structural validator, not the semantic linter.

## Current Auth Resolution Code Reference

For the implementer's reference, here's how auth currently flows:

### Two auth paths

1. **`inject_auth_into_params`** (executor.rs line 2011) — used by command, python, and other non-HTTP executors. Resolves auth and injects `.auth.*` into the params JSON so the executor's jaq expressions can reference them.

2. **`inject_adapter_auth`** (executor.rs line 2103) — used by REST and GraphQL executors. Returns an `AuthInjection` struct with headers, query params, and body params that get merged into the HTTP request.

### Cookie provider matchmaking

- `select_cookie_provider` (executor.rs ~line 2185) — scans all installed skills for `provides: [{ service: "cookies" }]`, picks one or errors if multiple.
- `resolve_cookie_auth_cached` (executor.rs ~line 2106) — checks in-memory `COOKIE_CACHE`, on miss calls `call_cookie_provider`, caches result.
- `call_cookie_provider` (executor.rs ~line 2246) — invokes the provider's `via` operation (e.g., `cookie_get`) with `domain` and `names`.
- `COOKIE_CACHE` — `Mutex<HashMap<String, CachedCookies>>` keyed by `"domain::provider_id"`.
- `invalidate_cookie_cache` — clears cached cookies for a domain on 401/403 retry.

None of this changes in v1. The same functions are called — they just get their `CookieAuth` from `connection.cookies` instead of `skill.auth.cookies`.

### Credential resolution (header/body/query auth)

- `resolve_credential` (executor.rs) — reads from the credential JSON store by skill ID and optional account name.
- Credentials are injected under `.auth.*` in the params context.
- For connection-model skills, credentials would still be stored per skill ID. If a skill has multiple connections that need different credentials, that's a v2 concern (likely separate credential store entries keyed by `skill_id::connection_name`).

## Migration Test: Goodreads

After building the runtime support, migrate `skills/goodreads/readme.md`:

1. Replace the top-level `auth:` block with `connections:` (graphql + web).
2. Replace all `auth: none` per-operation overrides with `connection: graphql`.
3. Add `connection: web` to operations that need cookies.
4. Remove all per-operation `auth: none` lines.

Before:

```yaml
auth:
  cookies:
    domain: ".goodreads.com"
    names: ["session_id", "__Secure-user_session"]
  optional: true
  label: Goodreads Session
  help_url: https://www.goodreads.com/user/sign_in

operations:
  search_books:
    auth: none
    command:
      binary: python3
      args: ["./public_graph.py", "search_books", ...]
      working_dir: .
      timeout: 15
```

After:

```yaml
connections:
  graphql:
    description: "Public AppSync GraphQL — API key auto-discovered from JS bundles"
  web:
    description: "Goodreads user cookies for viewer-scoped data"
    cookies:
      domain: ".goodreads.com"
      names: ["session_id", "__Secure-user_session"]
    label: Goodreads Session
    help_url: https://www.goodreads.com/user/sign_in

operations:
  search_books:
    connection: graphql
    python:
      module: ./public_graph.py
      function: search_books
      args:
        query: .params.query
        limit: '.params.limit // 10'
```

Note: this migration also assumes the Python executor is built (separate handoff at `docs/python-executor-handoff.md`). If the Python executor isn't ready yet, keep `command:` blocks but still migrate from `auth:` to `connections:`.

Verify with:

```bash
npm run validate -- goodreads
npm run mcp:test -- goodreads --verbose
```

## Full Migration Scope

Skills that would benefit from `connections:` (they have mixed auth today):

| Skill | Current hack | Proposed connections |
|---|---|---|
| **goodreads** | `auth: cookies + optional`, 6 ops with `auth: none` | `graphql` (no auth) + `web` (cookies) |
| **austin-boulder-project** | `auth: header + optional`, 1 op with `auth: none` | `api` (no auth) + `account` (header) |
| **moltbook** | `auth: header + optional`, 8 ops with `auth: none` | `api` (no auth) + `account` (header) |
| **here-now** | `auth: header + optional`, 1 op with `auth: none` | `api` (no auth) + `account` (header) |

Skills that stay on `auth:` unchanged (single auth method, no per-operation overrides):

All other authenticated skills: exa, todoist, linear, brave, serpapi, gandi, porkbun, firecrawl, anthropic-api, openrouter, posthog, logo-dev, gmail, claude, chase, amazon.

Skills with `auth: none` stay unchanged (playwright, kitty, github, macos-control, etc.).

## CONTRIBUTING.md Updates

After the feature is built and Goodreads is migrated, update `CONTRIBUTING.md`:

1. Add a `## Connections` section (peer to Auth section) explaining when to use `connections:` vs `auth:`.
2. Add the convention: `graphql` for API connections, `web` for cookie-authenticated website connections, `api` for public API connections, `account` for credential-authenticated connections.
3. Update the Auth section to note that per-operation `auth: none` is the old pattern; `connections:` is preferred for new multi-auth skills.
4. Add Goodreads as a "leading by example" reference for the connections pattern.
5. Update the Checklist to include: "Multi-auth skill uses `connections:`, not `auth: + auth: none` overrides."

## Build Order

This feature depends on nothing else, but pairs well with the Python executor (`docs/python-executor-handoff.md`). Recommended order:

1. **Python executor** — build and test with existing `command:` → `python:` migration on Goodreads.
2. **Connections v1** — build and test with `auth:` → `connections:` migration on Goodreads.
3. Goodreads becomes the showcase for both features working together.

Either can be built independently. The Goodreads migration is cleanest when both are done.

## Repos

- Engine (Rust): `/Users/joe/dev/agentos`
- Skills (YAML + Python): `/Users/joe/dev/agentos-community`
