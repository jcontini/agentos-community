# Reverse Engineering — Auth & Credentials

How to log into things, get API keys, and store credentials — for any web service.

This is Layer 3 of the reverse-engineering docs:

- **Layer 1: Transport** — [1-transport](../1-transport/index.md)
- **Layer 2: Discovery** — [2-discovery](../2-discovery/index.md)
- **Layer 3: Auth & Credentials** (this file)
  - [nextauth.md](./nextauth.md) — NextAuth.js / Auth.js deep dive
  - [workos.md](./workos.md) — WorkOS auth pattern
- **Layer 4: Content** — [4-content](../4-content/index.md)
- **Layer 5: Social Networks** — [5-social](../5-social/index.md)
- **Layer 6: Desktop Apps** — [6-desktop-apps](../6-desktop-apps/index.md)

---

## How web auth works

Every web login — from a 2005 PHP app to a 2026 Next.js SPA — does the same
three things:

1. **You prove who you are** (type a password, click a link, enter a code)
2. **The server gives you a cookie** (session token, JWT, whatever)
3. **You send that cookie with every request**

That's it. The mechanism varies — form POSTs, fetch calls, OAuth redirects —
but the end result is always a cookie in your browser.

### The two submission patterns

When you click "Submit" on a login form, one of two things happens:

**Form POST (the classic).** The browser sends an HTML form POST, the server
responds with a redirect (302), and the browser follows it. Cookies get set
along the way. This is the oldest pattern on the web and still used everywhere,
including modern frameworks like NextAuth.

```
Browser: POST /login { email, password }
Server:  302 → /dashboard  (Set-Cookie: session=abc123)
Browser: GET /dashboard (Cookie: session=abc123)
```

**Fetch/XHR (the SPA way).** JavaScript makes an async request, the page stays
loaded, and the response is handled in JS. The page might update without a
full navigation.

```
JS:      fetch('/api/login', { method: 'POST', body: { email, password } })
Server:  200 { token: "abc123" }
JS:      stores token, updates UI
```

Both are straightforward. When reverse engineering, you just need to figure out
which one a site uses, then replay it.

### Cookies

A cookie is a name-value pair the server sends with `Set-Cookie` and the
browser sends back with every request. The attributes control where and how:

| Attribute | What it means | HTTPX impact |
|-----------|--------------|--------------|
| `HttpOnly` | JS can't read it | Doesn't affect HTTPX (only matters in browsers) |
| `Secure` | HTTPS only | Use `https://` URLs |
| `SameSite=Lax` | Sent on navigations, not cross-site POSTs | HTTPX sends it normally |
| `Domain=.example.com` | Works on all subdomains | Important when auth and dashboard are on different subdomains |
| Expiry | Session (until browser close) or persistent (date) | HTTPX doesn't care — just send the cookie |

**Cross-domain cookies:** When auth lives at `auth.exa.ai` and the dashboard
at `dashboard.exa.ai`, the session cookie is scoped to `.exa.ai` so both
subdomains can use it. When extracting cookies, always check the domain —
`.exa.ai` works everywhere, `auth.exa.ai` only works on auth.

### CSRF tokens

Sites protect against forged requests by requiring a CSRF token — a secret
value the server generates and the client must include in form submissions.

The pattern is always the same:
1. Fetch the token (from an endpoint, a meta tag, a hidden form field, or a cookie)
2. Include it in your POST (as a form field, header, or both)

```python
csrf = client.get("/api/auth/csrf").json()["csrfToken"]
client.post("/api/auth/signin/email", data={"email": email, "csrfToken": csrf})
```

**The token and cookie must come from the same request.** If you fetch the
token with one HTTPX client and try to use it with another, the server will
reject it because the CSRF cookie doesn't match.

Where to find CSRF tokens during discovery:

```
# API endpoint (NextAuth)
evaluate { script: "fetch('/api/auth/csrf').then(r=>r.json()).then(d=>JSON.stringify(d))" }

# Meta tag
evaluate { script: "document.querySelector('meta[name=csrf-token]')?.content" }

# Hidden form fields
evaluate { script: "JSON.stringify(Array.from(document.querySelectorAll('input[type=hidden]')).map(i => ({name: i.name, value: i.value.substring(0,20)+'...'})))" }
```

---

## The credential bootstrap

This is the end-to-end flow for getting credentials from a web dashboard.
Every dashboard skill follows these five steps.

### 1. Navigate to the dashboard

Go to the dashboard URL (not the auth URL directly). The dashboard redirects
to auth with the right callback URL.

```
get_webpage { url: "https://dashboard.example.com", wait_until: "domcontentloaded" }
# → redirects to https://auth.example.com/?callbackUrl=https://dashboard.example.com/
```

If it lands on a Cloudflare challenge page, that's fine — the Playwright
browser solves it automatically and you get a `cf_clearance` cookie.

### 2. Figure out how to log in

Check what login methods are available:

```
evaluate { script: "fetch('/api/auth/providers').then(r=>r.json()).then(d=>JSON.stringify(Object.keys(d)))" }
```

Inspect the form:

```
inspect { selector: "form" }
```

This tells you:
- **Email + code** → usually fully HTTPX-replayable (see below)
- **Email + password** → replay entirely with HTTPX
- **Google/GitHub OAuth** → Playwright for the consent screen, then cookies
- **SSO (WorkOS, Okta)** → see vendor guides

### 3. Complete the login

**Try HTTPX first.** Many email+code flows that appear browser-only are actually
fully replayable. The key technique is scanning the JS bundles for custom
verification endpoints (e.g. `/api/verify-otp`) and using the Navigation API
interceptor to discover token formats. See
[Discovery: JS Bundle Scanning](../2-discovery/index.md#js-bundle-scanning) and
[Discovery: Navigation API Interception](../2-discovery/index.md#navigation-api-interception).

```python
# Example: Exa email+code login — no browser needed
# 1. Trigger code email
csrf_token = client.get(f"{AUTH_BASE}/api/auth/csrf").json()["csrfToken"]
client.post(f"{AUTH_BASE}/api/auth/signin/email", data={"email": email, "csrfToken": csrf_token, ...})

# 2. Agent reads code from email (Gmail, etc.)

# 3. Verify code via custom endpoint
resp = client.post(f"{AUTH_BASE}/api/verify-otp", json={"email": email, "otp": code})
data = resp.json()  # {hashedOtp, rawOtp}
token = f"{data['hashedOtp']}:{data['rawOtp']}"

# 4. Hit the standard callback with the constructed token
client.get(f"{AUTH_BASE}/api/auth/callback/email?token={token}&email={email}&callbackUrl=...")
# → session cookie is now set on the client
```

**Fall back to Playwright** only for flows that genuinely require a browser
(Google OAuth consent screens, CAPTCHAs, or complex multi-step redirects).
Use `type` (not `fill`) for input fields on React forms.

If the login involves a verification code from email, the agent checks email
between steps.

### 4. Grab the cookies

```
cookies { domain: ".example.com" }
```

You want the session cookie (usually `next-auth.session-token`, `session`,
`auth_token`, etc.) and optionally `cf_clearance` for Cloudflare.

Validate it works:

```python
with httpx.Client(http2=True, cookies={"next-auth.session-token": token}) as client:
    session = client.get("https://dashboard.example.com/api/auth/session").json()
    assert session.get("user"), "Session invalid"
```

### 5. Hit the dashboard APIs

Navigate to the API keys page and capture what the frontend calls:

```
capture_network { url: "https://dashboard.example.com/api-keys", pattern: "**/api/**", wait: 5000 }
```

This typically reveals endpoints for:
- Listing API keys
- Team/org info (rate limits, billing, usage)
- User profile

**Always read the full API response.** Dashboards mask values in the UI
(showing `9d2e4b••••••`) but the API often returns them in full. Exa's
`/api/get-api-keys` returns the complete API key as the `id` field — the UI
masking is purely client-side.

### 6. Store credentials

Return them via `__secrets__` so the engine stores them securely:

```python
return {
    "__secrets__": [{
        "issuer": "api.example.com",
        "identifier": email,
        "item_type": "api_key",
        "label": "Example API Key",
        "source": "example-skill",
        "value": {"key": api_key},
        "metadata": {
            "masked": {"key": api_key[:6] + "••••••••"},
            "dashboard_url": "https://dashboard.example.com/api-keys",
        },
    }],
    "__result__": {"status": "authenticated", "identifier": email},
}
```

The engine writes to the credential store, creates an account entity on the
graph, and strips `__secrets__` before the response reaches the agent.

---

## Observing network traffic

Three tools, each for a different situation.

### `capture_network` — what the page calls on load

Navigate to a URL and record all fetch/XHR traffic for a few seconds.

```
capture_network { url: "https://dashboard.exa.ai/api-keys", pattern: "**/api/**", wait: 5000 }
```

Use this to discover dashboard APIs, auth endpoints, and data shapes. Good
patterns to filter with:

```
"**/api/**"         REST APIs
"**graphql**"       GraphQL endpoints
"**appsync-api**"   AWS AppSync
```

### Fetch interceptor — what a button click triggers

When you need to see what happens after a user interaction (like clicking
"Create Key"), inject this before clicking:

```
evaluate { script: "window.__cap = []; const orig = window.fetch; window.fetch = async (...a) => { const req = { url: typeof a[0]==='string' ? a[0] : a[0]?.url, method: a[1]?.method||'GET' }; const r = await orig(...a); const c = r.clone(); req.status = r.status; req.body = (await c.text()).substring(0,3000); window.__cap.push(req); return r; }; 'ok'" }

click { selector: "button#create-key" }

evaluate { script: "JSON.stringify(window.__cap)" }
```

### Form inspection — what a form POST sends

If the fetch interceptor captures nothing but the browser navigated somewhere
new, the form did a native POST (full page navigation). Just inspect the form
to see what it sends:

```
evaluate { script: "JSON.stringify(Array.from(document.querySelectorAll('form')).map(f => ({ action: f.action, method: f.method, inputs: Array.from(f.querySelectorAll('input')).map(i => ({ name: i.name, type: i.type, value: i.value ? '(has value)' : '(empty)' })) })))" }
```

This gives you the `action` URL, the `method`, and all input fields including
hidden ones (CSRF tokens, honeypots).

After the form submits, the browser lands on a new page. Check where you ended
up (`url`) and grab the cookies (`cookies { domain: "..." }`). That's all
you need — the form POST did its job and set the session cookies.

### Quick reference

```
Page load traffic?         → capture_network
Button click / async?      → Fetch interceptor
Nothing captured + URL changed? → Native form POST — inspect the <form>, then just grab the cookies after
```

---

## Replaying with HTTPX

Once you understand what the browser does, replay it with HTTPX. The goal is
to get the same cookies without a browser.

### Form POSTs

```python
with httpx.Client(http2=True, follow_redirects=True, timeout=30) as client:
    resp = client.post("https://auth.example.com/api/auth/login", data={
        "email": email,
        "password": password,
        "csrfToken": csrf_token,
    })
    session_cookies = dict(client.cookies)
```

HTTPX with `follow_redirects=True` handles the redirect chain automatically —
same as the browser. The cookies accumulate on the client.

### Fetch/XHR calls

```python
resp = client.post("https://api.example.com/auth/login", json={
    "email": email, "password": password
})
token = resp.json()["token"]
```

### When HTTPX replay doesn't work

Sometimes the server does something specific to browser requests that HTTPX
can't replicate (custom redirect handling, Cloudflare challenges, JS-dependent
cookie setting). When that happens:

1. **Use Playwright for that step.** Let the browser handle it.
2. **Extract the cookies** from Playwright after.
3. **Use HTTPX for everything else** (dashboard APIs, data extraction, etc.)

This isn't a workaround — it's the right architecture. Playwright handles the
login, HTTPX handles the work. Each tool does what it's good at.

| Situation | Solution |
|-----------|----------|
| Standard form POST or API call | HTTPX replay |
| Custom OTP/code verification | Scan JS bundles for custom endpoints → HTTPX replay (see [discovery](../2-discovery/index.md#js-bundle-scanning)) |
| Google OAuth consent screen | Playwright first login → cookies → HTTPX after |
| Cloudflare JS challenge | Playwright or `brave-browser.cookie_get` for `cf_clearance` |
| Vercel Security Checkpoint (`429`) | Switch to `httpx(http2=False)` — purely a JA4 fingerprint issue |
| CAPTCHA | Cookies from user's real browser session |
| Unknown client-side token construction | Navigation API interceptor → read the actual URL (see [discovery](../2-discovery/index.md#navigation-api-interception)) |

---

## Working with Playwright

Practical notes for using the Playwright skill during discovery.

### Use `type`, not `fill`, for React forms

React manages input state through synthetic events. `fill` sets the DOM value
directly, bypassing React — the component state stays empty and submit buttons
stay disabled. `type` sends real keystrokes that trigger `onChange` handlers.

```
# React form — use type
type { selector: "input[type=email]", text: "user@example.com" }

# Plain HTML form — either works
fill { selector: "input[type=email]", value: "user@example.com" }
```

If the submit button is disabled after entering text, you probably need `type`.

### Watch for honeypot fields

Some login forms have hidden inputs designed to catch bots:

```html
<input name="website" type="text" style="display:none">
```

These are invisible to users but bots that fill every field get caught. In
HTTPX replay, **never include these fields**. Common names: `website`, `url`,
`homepage`, `company`, `fax`.

If your HTTPX replay silently fails (200 response but nothing happens), check
for honeypot fields you might be filling.

### Navigate to dashboard, not auth

Always start at the dashboard URL. The auth domain needs the `callbackUrl`
parameter (set by the dashboard redirect) to know where to send you after
login. Going to auth directly often shows "accessed incorrectly" errors.

### Clearing state for a fresh run

```
clear_cookies { domain: ".example.com" }
```

Useful when existing cookies skip you past the login page and you need to
observe the full flow from scratch.

---

## Auth patterns

### NextAuth.js / Auth.js

The most common pattern for Next.js dashboards. Recognized by `/api/auth/*`
endpoints and `next-auth.*` cookies.

**Quick identification:**
- `GET /api/auth/csrf` returns a CSRF token
- `GET /api/auth/providers` lists available login methods
- Session cookie: `next-auth.session-token` (encrypted JWT, ~30 day expiry)

**Email login flow (fully HTTPX for custom OTP sites):**
1. `GET /api/auth/csrf` → CSRF token (HTTPX)
2. `POST /api/auth/signin/email` → triggers email (HTTPX)
3. `POST /api/verify-otp` → verify code, get token components (HTTPX)
4. `GET /api/auth/callback/email?token=...` → session cookie set (HTTPX)

The key insight: many NextAuth sites with custom OTP code entry have a hidden
`/api/verify-otp` endpoint discoverable via JS bundle scanning. The callback
token format (`hashedOtp:rawOtp`) was discovered using the Navigation API
interceptor. See [nextauth.md](./nextauth.md) for the full deep dive.
Reference implementation: `skills/exa/`.

### AWS Cognito

Common in gym/fitness SaaS (Approach, Mindbody, etc.). Pure AWS API calls —
no browser needed at all.

```python
resp = httpx.post(
    "https://cognito-idp.us-east-1.amazonaws.com/",
    headers={
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        "Content-Type": "application/x-amz-json-1.1",
    },
    content=json.dumps({
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": client_id,
        "AuthParameters": {"USERNAME": email, "PASSWORD": password},
    }).encode(),
)
tokens = resp.json()["AuthenticationResult"]
# Use tokens["AccessToken"] as Bearer token
```

Find the `ClientId` in the app's JS bundle — search for `userPoolId` or
`userPoolClientId`.

### WorkOS

B2B auth platform. Supports SSO, social login, and email. Recognized by
`workos_id` in JWT claims.

See [workos.md](./workos.md) for the full deep dive.

### Cookie-based sessions (generic)

For any site that uses session cookies without a framework like NextAuth:

1. Walk through the login in Playwright
2. Extract cookies: `cookies { domain: ".example.com" }`
3. Use them in HTTPX: `httpx.Client(cookies={...})`

Reference implementations:
- `skills/claude/claude-login.py` (Cloudflare-protected)
- `skills/amazon/amazon.py` (tiered cookie architecture, Siege bypass)

### Tiered cookie architectures

Large services like Amazon use multiple cookie tiers for different access levels:

| Tier | Cookies | Access |
|------|---------|--------|
| Session | `session-id`, `session-token`, `ubid-main` | Browsing, search |
| Persistence | `x-main` | "Remember me" across sessions |
| Authentication | `at-main` (`Atza\|...`), `sess-at-main` | Account pages, order history |
| SSO | `sst-main` (`Sst1\|...`), `sso-state-main` | Cross-service auth |

When building a skill against a tiered service, you need the **full cookie jar**
from a logged-in browser — not just the session cookie. The auth tokens are
interdependent and the server validates them together.

Some cookies should be **excluded** (see [1-transport](../1-transport/index.md)
for cookie stripping) — encryption trigger cookies, WAF telemetry, etc. But
the auth-tier cookies must all be present.

---

## Auth boundaries

Not every operation needs a login. During discovery, classify each endpoint:

| Tier | Description | Example |
|------|-------------|---------|
| **Public** | Works with just a frontend API key | Goodreads search, Exa search API |
| **Suggested auth** | Richer results with a session, but works without | Goodreads reviews (adds `viewerHasLiked`) |
| **Required auth** | Fails without session cookies | Dashboard APIs, mutations, user-specific data |

To map boundaries: send each request without auth. If you get data, it's
public. If you get partial data with errors on some fields, it's suggested
auth. If you get a 401/403 or an auth error, it's required.

In the skill manifest, mark public operations with `auth: none`:

```yaml
operations:
  search:         # public — no cookies
    auth: none
  get_api_keys:   # requires dashboard session
    connection: dashboard
```

---

## Runtime config discovery

Some services rotate API keys or endpoints when they deploy. For these, build
a multi-tier discovery chain that self-heals:

```
Tier 1: Cache           instant, works until config rotates
Tier 2: Bundle extract  1-2s, parse the JS bundle for config
Tier 3: Browser capture 10-15s, load the page and capture network
Tier 4: Hardcoded       instant, but may be stale
```

> **Note:** File-based caching has been replaced by sandbox storage — the
> executor reads/writes `cache` vals on the skill's graph node.
> See `spec/sandbox-storage.md`.

### Implementation

```python
def discover_runtime(**kwargs) -> dict:
    cached = _load_cache()
    if cached:
        return cached

    config = discover_from_bundle(kwargs.get("html_text"))
    if config:
        _save_cache(config)
        return config

    config = discover_via_browser(kwargs.get("page_url"))
    if config:
        _save_cache(config)
        return config

    return {"endpoint": FALLBACK_ENDPOINT, "api_key": FALLBACK_API_KEY}
```

### Multi-environment bundles

Production JS bundles often ship configs for all environments. Pick Prod:

| Signal | Example |
|--------|---------|
| `shortName` field | `"shortName": "Prod"` |
| Ads enabled | `"showAds": true` |
| Analytics enabled | `"publishWebVitalMetrics": true` |

Reference: `skills/goodreads/public_graph.py` `discover_from_bundle()`.

---

## Examples

| Skill | Pattern | What to learn from it |
|-------|---------|----------------------|
| `skills/amazon/` | Tiered cookie auth, Siege encryption bypass, `SESSION_EXPIRED` retry | Full client hints, cookie stripping for anti-bot, session warming, provider retry convention |
| `skills/exa/` | NextAuth email code → fully HTTPX (no browser) → API keys | JS bundle scanning for custom endpoints, Navigation API interception, OTP token format discovery, Vercel `http2=False` bypass |
| `skills/goodreads/` | Multi-tier discovery, AppSync, auth boundary mapping | Bundle extraction, config rotation, public vs auth operations |
| `skills/claude/` | Cloudflare-protected cookie extraction | Stealth Playwright settings, HttpOnly cookies via CDP |
| `skills/austin-boulder-project/` | Bundle-extracted API key, tenant namespace | JS config scanning, namespace-as-auth |

### Vendor guides

| Guide | When to read it |
|-------|----------------|
| [nextauth.md](./nextauth.md) | Sites with `/api/auth/*` endpoints, `next-auth.*` cookies |
| [workos.md](./workos.md) | Sites with `workos_id` in JWT claims, WorkOS session IDs |
| [macos-keychain.md](./macos-keychain.md) | Native macOS apps, Electron Safe Storage, Google OAuth tokens, full credential audit |
