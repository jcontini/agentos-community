# Auth Flows

When a skill needs credentials from a web dashboard (API keys, session tokens), the flow is: **discover with Playwright, implement with HTTPX**. For steps that HTTPX can't replay (native form POSTs, complex redirect chains), the agent uses Playwright for that step and HTTPX for everything after.

## The pattern

1. **Discover** — use the Playwright skill interactively to walk through the login/signup flow. `capture_network` reveals endpoints, `cookies` shows what session cookies get set, `inspect` shows form structure.
2. **Implement** — write the login flow as Python + `httpx` in the skill's `.py` file. Use `http2=True`, `follow_redirects=True`, and inject cookies from `params.auth.cookies` or `_call` to other skills (e.g. Gmail for magic links, `brave-browser` for Google session cookies).
3. **Store** — return extracted credentials via `__secrets__` so the engine stores them securely. The LLM never sees raw secret values.
4. **Test** — `test-skills.cjs` should work without a running browser. If your skill needs Playwright at runtime, rethink the approach.

## Dashboard connections

Skills with web dashboards declare a `dashboard` connection alongside their `api` connection:

```yaml
connections:
  api:
    base_url: "https://api.example.com"
    auth:
      type: api_key
      header: { x-api-key: .auth.key }

  dashboard:
    base_url: "https://dashboard.example.com"
    auth:
      type: cookies
      domain: ".example.com"
      login:
        - sso: google
        - email_link: true
```

All auth goes under a single `auth:` key with a `type` discriminator (`api_key`, `cookies`, `oauth`). The `login` block declares available login methods. Login operations are Python functions that execute the flow with HTTPX. See `specs/auth-model.md` in the engine repo for the unified auth model, and `specs/sso-credential-bootstrap.md` for the end-to-end bootstrap flow.

## Secret-safe credential return

Login and API key extraction operations return credentials via `__secrets__`:

```python
def get_api_key(*, _call=None, **params):
    # ... HTTPX calls to get the key ...
    return {
        "__secrets__": [{
            "issuer": "api.example.com",
            "identifier": "user@example.com",
            "item_type": "api_key",
            "label": "Example API Key",
            "source": "example",
            "value": {"key": api_key},
            "metadata": {"masked": {"key": "••••" + api_key[-4:]}}
        }],
        "__result__": {"status": "authenticated", "identifier": "user@example.com"}
    }
```

The engine writes `__secrets__` to the credential store, creates an account entity on the graph, and strips the secrets before the MCP response reaches the agent.

## Cookie resolution chain

When the engine resolves cookie auth for a connection, it follows this order:

1. **Credential store** — check `credentials.sqlite` for a stored cookie matching the issuer (derived from the connection's `base_url`) and the requested `names` filter.
2. **Providers** — if the store has nothing (or on retry after 401/403), query all installed skills that `provides: - auth: cookies`. Three providers exist today: **Brave** (SQLite cookie DB), **Firefox** (SQLite cookie DB), **Playwright** (persistent Chromium session via CDP).
3. **Fail** — if no provider can supply the cookies, raise a credential error.

Playwright is the primary provider for cookies acquired through login automation. After a successful login flow, cookies live in Playwright's persistent browser context. The engine can query them via `playwright.cookies` the same way it queries `brave-browser.cookie_get`. The `store_session_cookies` step persists them to the credential store so future runs don't need Playwright.

On 401/403 (or Python exceptions containing `401`, `403`, `unauthorized`, `forbidden`), the engine invalidates the store entry and retries with a fresh provider query. See `connections.md` for the Python exception convention.

## Key rules

- **Never import Playwright in skill Python code.** Playwright is a separate skill for investigation. Skill operations use `httpx`.
- **Never expose secrets in `__result__`.** Secrets go in `__secrets__` only. The agent sees masked versions via `metadata.masked`.
- **`_call` is same-skill only.** It dispatches to sibling operations within the same skill (e.g. Gmail's `list_emails` calling `get_email`). It cannot call operations in other skills.
- **Cross-skill coordination goes through the agent.** If a login flow needs email access, the operation yields back to the agent (see below), and the agent uses whatever email capability is available.

## Agent-in-the-loop auth flows

Some login flows require input the skill can't obtain on its own — a verification code from email, an SMS code, or user approval. These flows must **yield back to the agent** rather than trying to handle the dependency internally.

### Why not handle it in Python?

- `_call` is same-skill only — Python can't call `gmail.search_emails` from inside `exa.py`
- Hardcoding a specific email skill (Gmail) couples the skill to that provider — what if the user uses Mimestream?
- Blocking in Python for 60 seconds while polling gives the agent no visibility or control

### The multi-step pattern

Split the flow so the agent orchestrates between HTTPX operations and Playwright when needed:

```
Agent calls skill.send_login_code({ email })
  → Python/HTTPX: CSRF + trigger verification email
  → Returns: { status: "code_sent", hint: "..." }

Agent checks email (any provider) and extracts the code

Agent uses Playwright to complete login (if HTTPX can't replay the code submission)
  → Navigate to login page, type email, submit, type code, submit
  → Extract cookies from browser

Agent calls skill.store_session_cookies({ email, session_token, ... })
  → Python/HTTPX: validates session, stores via __secrets__
```

The `hint` field tells the agent what to search for (e.g. "subject 'Sign in to Exa Dashboard' from exa.ai"). The agent knows how to search email — it picks the right provider and extracts the code.

**Why Playwright for the code submission?** Some auth implementations (e.g. Exa's NextAuth) submit verification codes via a native HTML form POST that HTTPX cannot replay — the server-side handling differs from a programmatic POST. The fetch interceptor captures nothing, but the browser navigates successfully. When this happens, use Playwright for the form submission step and HTTPX for everything else.

### When to use this pattern

- Email verification codes (Exa, any NextAuth email provider)
- SMS/TOTP verification
- OAuth consent that requires user approval
- Any flow where the skill needs external input it can't obtain via `_call`
- Any step where HTTPX replay fails but the browser works (native form POSTs, complex redirect chains)

### Example: Exa

See `skills/exa/exa.py`:
- `send_login_code` — triggers the verification email (HTTPX)
- `store_session_cookies` — validates and stores browser-extracted session cookies (HTTPX)
- The agent uses Playwright between these two operations to enter the code and complete login

### Future: session-scoped state

Passing CSRF tokens through params works but is noisy. The target is session-scoped temporary storage (tied to the MCP/agent session) so Python can write state in step 1 and read it in step 2 without the agent seeing the plumbing. See the engine roadmap for "Session-scoped state for auth flows."

For the full reverse engineering methodology, see:
- [Auth & Runtime](../reverse-engineering/3-auth/README.md) — credential bootstrap lifecycle, network interception, cookie mechanics, CSRF patterns, web navigation
- [NextAuth.js guide](../reverse-engineering/3-auth/nextauth.md) — vendor-specific patterns for NextAuth/Auth.js sites
- [WorkOS guide](../reverse-engineering/3-auth/workos.md) — vendor-specific patterns for WorkOS-based auth
