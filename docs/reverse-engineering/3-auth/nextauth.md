# NextAuth.js (Auth.js) Pattern

NextAuth.js (rebranded to Auth.js) is the most popular auth library for Next.js
apps. Many SaaS dashboards use it for email login, Google SSO, and enterprise
auth (via WorkOS or similar). Understanding its conventions accelerates reverse
engineering because the endpoint structure, cookie names, and flow mechanics
are predictable.

Part of [Layer 3: Auth & Runtime](./index.md). Discovered during the
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

### Step 2: Code/token submission

**Standard NextAuth** uses a magic link that hits:
```
GET /api/auth/callback/email?callbackUrl=...&token=TOKEN&email=EMAIL
```
Where `TOKEN` is the raw verification token. NextAuth hashes it as
`SHA256(token + NEXTAUTH_SECRET)` and compares with the stored hash.

**Custom OTP implementations** (e.g. Exa) display a 6-digit code entry page
instead of a magic link. These typically have a custom verification endpoint:

```
POST /api/verify-otp
Body: {"email": "user@example.com", "otp": "123456"}
→ {"email": "...", "hashedOtp": "$2a$10$...", "rawOtp": "123456"}
```

The client-side JS then constructs the NextAuth callback token from the
response and redirects to the standard callback:

```
GET /api/auth/callback/email?token=HASHED_OTP:RAW_OTP&email=EMAIL&callbackUrl=...
```

The token format is `{hashedOtp}:{rawOtp}` — bcrypt hash, colon, raw code.
This is fully replayable via HTTPX. No browser needed.

### Discovery playbook for custom OTP flows

When the standard NextAuth callback fails with `error=Verification`, the site
has a custom OTP layer. Follow these steps to crack it:

**Step A: Scan JS bundles for custom endpoints**

```python
# Search terms that reveal custom auth endpoints
scan_bundles(auth_url, [
    "verify-otp", "verify-code", "confirm-code",     # custom verification
    "callback/email", "hashedOtp", "rawOtp",          # token construction
    "fetch(", "/api/",                                 # general API calls
])
```

Look for `fetch("/api/verify-...")` calls in the bundle context. The
surrounding code usually reveals the request shape and response handling.

**Step B: Read the library source**

Check what the server expects. For NextAuth, the key file is
[`callback/index.ts`](https://github.com/nextauthjs/next-auth/blob/main/packages/core/src/lib/actions/callback/index.ts).
The email handler does `createHash(token + secret)` — this tells you the
token parameter must match what the server originally stored.

**Step C: Intercept the client-side token construction**

If the bundle shows the endpoint but the token construction is complex or
spread across minified closures, use the Navigation API interceptor:

```
evaluate { script: "navigation.addEventListener('navigate', (e) => { window.__intercepted_nav_url = e.destination.url; e.preventDefault(); }); 'interceptor installed'" }
```

Then trigger the action:
```
click { selector: "button:text-is('VERIFY CODE')" }
evaluate { script: "window.__intercepted_nav_url" }
```

The captured URL will contain the fully-assembled token, e.g.:
```
https://auth.exa.ai/api/auth/callback/email?token=$2a$10$...%3A123456&email=...
```

URL-decode it and the format is obvious: `{bcrypt_hash}:{raw_otp}`.

**Step D: Replay with HTTPX**

Now you know the full flow — reproduce it with HTTPX:
1. `POST /api/verify-otp` with `{email, otp}` → get `{hashedOtp, rawOtp}`
2. Construct `token = f"{hashedOtp}:{rawOtp}"`
3. `GET /api/auth/callback/email?token=...&email=...` → session cookie

See [Discovery: JS Bundle Scanning](../2-discovery/index.md#js-bundle-scanning)
and [Discovery: Navigation API Interception](../2-discovery/index.md#navigation-api-interception)
for the general techniques.

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
# Use http2=False for Vercel-hosted dashboards (Security Checkpoint blocks h2)
# Use http2=True for other hosts (CloudFront, plain Cloudflare, etc.)
with httpx.Client(
    http2=False,  # adjust per host — see 1-transport
    follow_redirects=True,
    cookies={"next-auth.session-token": session_token},
) as client:
    resp = client.get(f"{DASHBOARD_BASE}/api/get-api-keys")
```

The server decodes the JWT server-side and returns the session info via
`/api/auth/session`. See [Transport: http2 selection](../1-transport/index.md#when-to-use-http2false)
for how to determine the right setting per host.

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
[Playwright Discovery Gotchas](./index.md#honeypot-fields) for details.

### React forms need `type` not `fill`

NextAuth login pages built with React/Next.js require Playwright's `type`
command (real keystrokes) rather than `fill` (direct DOM manipulation). `fill`
bypasses React's synthetic event system and leaves form state empty. See
[Playwright Discovery Gotchas](./index.md#type-vs-fill-on-react-forms).

### Vercel Security Checkpoint

Many NextAuth dashboards are hosted on Vercel. Vercel's Security Checkpoint
blocks `httpx(http2=True)` outright — returning `429` with a JS challenge
page regardless of cookies or headers. The fix is `httpx(http2=False)`.

This is purely a JA4 TLS fingerprint issue. httpx's h2 fingerprint is
well-known to Vercel's bot detection. h1 is less distinctive and passes.
See [Layer 1: Transport](../1-transport/index.md#when-to-use-http2false)
for the full analysis.

Not every Vercel subdomain enables the checkpoint. Test each one — during
Exa reverse engineering, `auth.exa.ai` accepted h2 while `dashboard.exa.ai`
rejected it. The checkpoint is a per-project Vercel Firewall setting.

### Cloudflare protection

Some NextAuth sites sit behind Cloudflare (separate from Vercel's layer)
and set a `cf_clearance` cookie after a JS challenge. `cf_clearance` is
bound to the client's TLS fingerprint and IP — it only works from the
same fingerprint that solved the challenge.

In practice, for Vercel-hosted dashboards the `http2=False` fix is
sufficient and `cf_clearance` isn't needed. Store it if available (it's
cheap insurance), but don't depend on it for HTTPX access.

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

See [Dashboard APIs leak more than the UI](./index.md#dashboard-apis-often-leak-more-than-the-ui-shows)
for the general pattern.

---

## Real-world example: Exa

Exa (`dashboard.exa.ai` / `auth.exa.ai`) is the reference implementation for
this pattern in the agentOS skill library. **The entire email login flow is
browser-free** — every step uses HTTPX.

**Architecture:**
- Auth domain: `auth.exa.ai` (NextAuth.js, Vercel-hosted)
- Dashboard domain: `dashboard.exa.ai` (Vercel-hosted, Security Checkpoint enabled)
- Providers: `email`, `google`, `workos`
- Email verification: 6-digit OTP code (custom `/api/verify-otp` endpoint)
- Session: encrypted JWT in `next-auth.session-token` on `.exa.ai`
- Transport: `httpx(http2=False)` for dashboard (Vercel checkpoint blocks h2)

**Skill operations:**
- `send_login_code` — triggers verification email via HTTPX
- `verify_login_code` — verifies OTP code, constructs token, completes login (fully HTTPX)
- `store_session_cookies` — fallback for Google SSO (Playwright cookies)
- `get_api_keys` — lists keys (full values in `id` field) via HTTPX
- `get_teams` — team info, rate limits, credits via HTTPX
- `create_api_key` — creates a new key via HTTPX

**Key findings:**
- The `id` field in `/api/get-api-keys` is the full API key value (UUID format).
  The dashboard masks it, but the API returns it unmasked.
- The custom OTP endpoint (`POST /api/verify-otp`) was found via JS bundle
  scanning — it doesn't appear in any NextAuth documentation.
- The callback token format (`hashedOtp:rawOtp`) was discovered using the
  Navigation API interceptor in Playwright, then replayed entirely with HTTPX.

**How it was reverse-engineered (summary):**

1. **Identify framework:** `GET /api/auth/providers` → NextAuth
2. **Try standard flow:** `POST /api/auth/signin/email` → sends code OK;
   `GET /api/auth/callback/email?token=CODE` → `error=Verification` (6-digit
   code isn't the raw token NextAuth expects)
3. **Scan JS bundles:** search for `verify-otp`, `callback/email`, `fetch(`
   → found `POST /api/verify-otp` accepting `{email, otp}` returning
   `{hashedOtp, rawOtp}`
4. **Read library source:** NextAuth's `callback/index.ts` shows the server
   does `SHA256(token + secret)` — so the token must be the pre-hash value
5. **Intercept with Navigation API:** inject `navigation.addEventListener`,
   click "VERIFY CODE", capture the destination URL → token format is
   `{hashedOtp}:{rawOtp}` (bcrypt hash, colon, raw OTP)
6. **Replay with HTTPX:** `POST /api/verify-otp` → construct token →
   `GET /api/auth/callback/email?token=...` → session cookie set

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
