# NextAuth.js (Auth.js) Pattern

NextAuth.js (rebranded to Auth.js) is the most popular auth library for Next.js
apps. Many SaaS dashboards use it for email login, Google SSO, and enterprise
auth (via WorkOS or similar). Understanding its conventions accelerates reverse
engineering because the endpoint structure, cookie names, and flow mechanics
are predictable.

Part of [Layer 3: Auth & Runtime](./README.md). Discovered during the
[Exa skill](../../../skills/exa/readme.md) reverse engineering session.

---

## Recognizing NextAuth

Any of these signals indicate NextAuth:

| Signal | Example |
|--------|---------|
| Auth endpoints at `/api/auth/*` | `/api/auth/csrf`, `/api/auth/providers`, `/api/auth/session` |
| CSRF cookie | `__Host-next-auth.csrf-token` (value is `token%7Chash`) |
| Callback URL cookie | `__Secure-next-auth.callback-url` |
| Session cookie | `next-auth.session-token` (JWT, HttpOnly, ~30 day expiry) |
| Separate auth subdomain | `auth.example.com` with redirects to `dashboard.example.com` |
| Provider list endpoint | `GET /api/auth/providers` returns JSON with provider configs |

### Quick probe

```
capture_network { url: "https://auth.example.com", pattern: "**/api/auth/**", wait: 3000 }
```

If you see `/api/auth/csrf` and `/api/auth/providers` in the capture, it's NextAuth.

### Provider discovery

```
evaluate { script: "fetch('/api/auth/providers').then(r=>r.json()).then(d=>JSON.stringify(d))" }
```

Returns something like:

```json
{
  "email": { "id": "email", "name": "Email", "type": "email", "signinUrl": "/api/auth/signin/email" },
  "google": { "id": "google", "name": "Google", "type": "oauth", "signinUrl": "/api/auth/signin/google" },
  "workos": { "id": "workos", "name": "WorkOS", "type": "oauth", "signinUrl": "/api/auth/signin/workos" }
}
```

This tells you exactly which login methods are available before you try anything.

---

## Endpoint map

All endpoints live under the auth domain's `/api/auth/` prefix.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/csrf` | GET | Returns `{ csrfToken: "..." }` and sets the CSRF cookie |
| `/api/auth/providers` | GET | Lists available auth providers with their signin URLs |
| `/api/auth/signin/email` | POST | Triggers verification code/link email |
| `/api/auth/signin/google` | POST | Initiates Google OAuth redirect |
| `/api/auth/callback/email` | GET/POST | Handles email verification callback |
| `/api/auth/callback/google` | GET | Handles Google OAuth callback |
| `/api/auth/session` | GET | Returns current session (user info, expiry) |
| `/api/auth/signout` | POST | Destroys session |

### CSRF token

Every mutating request requires the CSRF token, obtained from `/api/auth/csrf`:

```python
resp = client.get(f"{AUTH_BASE}/api/auth/csrf")
csrf_token = resp.json()["csrfToken"]
```

The response also sets a `__Host-next-auth.csrf-token` cookie. The value is
`token%7Chash` — the token and a hash separated by `|` (URL-encoded as `%7C`).
Both the cookie and the `csrfToken` field in the POST body must match.

---

## Email verification flow

NextAuth's email provider sends a verification code (or sometimes a magic link,
depending on the site's configuration). The standard flow:

### Step 1: Trigger the email (HTTPX-compatible)

```python
csrf_token = _get_csrf_token(client)

client.post(
    f"{AUTH_BASE}/api/auth/signin/email",
    data={
        "email": email,
        "csrfToken": csrf_token,
        "callbackUrl": "https://dashboard.example.com/",
        "json": "true",
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
```

This sends the verification email. The response is typically `{ "url": "..." }`
pointing to a "check your email" page.

### Step 2: Code submission (varies by implementation)

**Standard NextAuth** uses a magic link that hits:
```
GET /api/auth/callback/email?callbackUrl=...&token=CODE&email=EMAIL
```

**Custom implementations** (e.g. Exa) render a code entry page where the user
types the 6-digit code. The form submits via a **native HTML form POST** — not
a `fetch()` call. This means:

- The fetch interceptor captures nothing
- HTTPX replay of the callback endpoint may fail
- Playwright handles it natively

**How to tell which one you're dealing with:**
1. After triggering the email, check what the verification page looks like
2. If it's a "check your email for a link" page → standard magic link flow
3. If it's a "enter your code" page with an `<input>` → code entry form
4. Install the fetch interceptor, enter the code, submit — if empty capture,
   it's a native form POST

### Step 3: Session establishment

After successful verification (either path), the server sets the
`next-auth.session-token` cookie and redirects to the callback URL.

Validate the session:

```python
resp = client.get(f"{DASHBOARD_BASE}/api/auth/session")
session = resp.json()
# { "user": { "email": "...", "id": "...", "teams": [...] }, "expires": "..." }
```

---

## Cookie anatomy

| Cookie | Domain | HttpOnly | Secure | SameSite | Expiry | Purpose |
|--------|--------|----------|--------|----------|--------|---------|
| `__Host-next-auth.csrf-token` | auth domain | Yes | Yes | Lax | Session | CSRF double-submit |
| `__Secure-next-auth.callback-url` | auth domain | Yes | Yes | Lax | Session | Where to redirect after auth |
| `next-auth.session-token` | `.parent-domain` | Yes | Yes | Lax | ~30 days | JWT session (the important one) |

**Cross-domain note:** The session token is typically scoped to the parent domain
(e.g. `.exa.ai`) so it works across both `auth.exa.ai` and `dashboard.exa.ai`.
The CSRF and callback cookies are scoped to the auth subdomain only.

For HTTPX replay, you only need `next-auth.session-token` for authenticated
API calls. The CSRF and callback cookies are only needed during the login flow
itself.

---

## Session token (JWT)

The `next-auth.session-token` is an encrypted JWT (JWE with `A256GCM`). You
can't decode it without the server's secret — but you don't need to. Just pass
it as a cookie to authenticated endpoints.

```python
with httpx.Client(
    http2=True,
    follow_redirects=True,
    cookies={"next-auth.session-token": session_token},
) as client:
    resp = client.get(f"{DASHBOARD_BASE}/api/get-api-keys")
```

The server decodes the JWT server-side and returns the session info via
`/api/auth/session`.

---

## Gotchas

### Auth subdomain vs dashboard domain

Many NextAuth sites separate auth and dashboard onto different subdomains.
Navigate to the **dashboard** domain (e.g. `https://dashboard.exa.ai`), not the
auth domain directly. The dashboard redirects to auth with the correct
`callbackUrl` parameter. Going to auth directly often shows "accessed
incorrectly" errors because the callback URL is missing.

### Honeypot fields

Some NextAuth login forms include hidden honeypot fields (e.g.
`input[name="website"]`). Never fill these in HTTPX replay. See
[Playwright Discovery Gotchas](./README.md#honeypot-fields) for details.

### React forms need `type` not `fill`

NextAuth login pages built with React/Next.js require Playwright's `type`
command (real keystrokes) rather than `fill` (direct DOM manipulation). `fill`
bypasses React's synthetic event system and leaves form state empty. See
[Playwright Discovery Gotchas](./README.md#type-vs-fill-on-react-forms).

### Cloudflare protection

NextAuth sites behind Cloudflare (common) set a `cf_clearance` cookie after
the JS challenge. For HTTPX replay:
- If the challenge was solved by Playwright, extract `cf_clearance` along with
  the session token
- If using stored cookies, `cf_clearance` may expire (typically 24h) — the
  session token lasts ~30 days but Cloudflare may block HTTPX after clearance
  expires
- For long-term access, you may need to re-solve the Cloudflare challenge
  periodically via Playwright or the user's real browser

---

## Dashboard API patterns

Once authenticated, NextAuth dashboards typically expose REST APIs under
`/api/`. These are standard Next.js API routes — no special auth headers needed,
just the session cookie.

Common patterns discovered during reverse engineering:

| Endpoint pattern | What it returns |
|-----------------|-----------------|
| `/api/auth/session` | User profile, team memberships, feature flags |
| `/api/get-api-keys` | API keys (may include full values!) |
| `/api/get-teams` | Team info, rate limits, billing, usage |
| `/api/create-api-key` | Creates a new key (POST, JSON body) |
| `/api/service-api-keys?teamId=` | Service-level keys (separate from user keys) |

**Always check raw API responses.** Dashboard UIs routinely mask sensitive
values (API keys, tokens) client-side, but the underlying API returns them in
full. During reverse engineering, use `capture_network` on authenticated pages
and read the complete JSON response bodies.

See [Dashboard APIs leak more than the UI](./README.md#dashboard-apis-often-leak-more-than-the-ui-shows)
for the general pattern.

---

## Real-world example: Exa

Exa (`dashboard.exa.ai` / `auth.exa.ai`) is the reference implementation for
this pattern in the agentOS skill library.

**Architecture:**
- Auth domain: `auth.exa.ai` (NextAuth.js)
- Dashboard domain: `dashboard.exa.ai`
- Providers: `email`, `google`, `workos`
- Email verification: 6-digit code (native form POST, not magic link)
- Session: encrypted JWT in `next-auth.session-token` on `.exa.ai`
- Cloudflare: `cf_clearance` on `.exa.ai`

**Skill operations:**
- `send_login_code` — triggers verification email via HTTPX
- `store_session_cookies` — validates and stores browser-extracted session
- `get_api_keys` — lists keys (full values in `id` field) via HTTPX
- `get_teams` — team info, rate limits, credits via HTTPX
- `create_api_key` — creates a new key via HTTPX

**Key finding:** The `id` field in `/api/get-api-keys` is the full API key
value (UUID format). The dashboard masks it, but the API returns it unmasked.

See `skills/exa/exa.py` and `skills/exa/readme.md` for the full implementation.

---

## Comparison with WorkOS

| Aspect | NextAuth | WorkOS |
|--------|----------|--------|
| Where it lives | In the app (Next.js API routes) | External auth service |
| JWT decoding | Encrypted (JWE), opaque | Standard JWT, decodable |
| Session storage | Cookie-based (JWT in cookie) | Cookie or token-based |
| Token refresh | Automatic via session cookie | Explicit refresh token flow |
| Identification | `/api/auth/*` routes, `next-auth.*` cookies | `workos` in JWT `iss`, `workos_id` claim |
| Multi-tenant | App-specific | Built-in organization/team support |

See [WorkOS Auth Pattern](./workos.md) for the WorkOS-specific methodology.
