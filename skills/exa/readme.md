---
id: exa
name: Exa
description: Semantic web search and content extraction
color: "#1F40ED"
website: "https://exa.ai"
privacy_url: "https://exa.ai/privacy"
terms_url: "https://exa.ai/terms"

connections:
  api:
    base_url: https://api.exa.ai
    domain: exa.ai
    auth:
      type: api_key
      header:
        x-api-key: .auth.key
    label: API Key
    help_url: https://dashboard.exa.ai/api-keys
  dashboard:
    base_url: https://dashboard.exa.ai
    domain: exa.ai
    auth:
      type: cookies
      domain: .exa.ai
      names:
      - next-auth.session-token
      account:
        check: check_session
      login:
      - email_code: true
      - sso: google

product:
  name: Exa
  website: https://exa.ai
  developer: Exa AI, Inc.

operations:
  search:
    wraps_as: search
    web_url: '"https://exa.ai/search?q=" + (.params.query | @uri)'
  read_webpage:
    web_url: .params.url

test:
  check_session:
    skip: true
  search:
    params:
      query: agentOS personal AI
      limit: 3
  read_webpage:
    params:
      url: https://exa.ai
---

# Exa

Semantic web search and content extraction. Neural search finds content by meaning, not just keywords.

## Setup

1. Get your API key from https://dashboard.exa.ai/api-keys
2. Add credential in AgentOS Settings → Providers → Exa

Or use the automated bootstrap flow (see Auth below).

## Features

- Neural/semantic search
- Fast content extraction
- Find similar pages
- Relevance scoring

## Usage

### search

Create a web search. Returns search results (index records, not full page content).

```
run({ skill: "exa", tool: "search", params: { query: "rust programming" } })
```

Results are `result` entities — snapshots of what the search engine knew about each URL.
To get full page content, follow up with `read_webpage` on a result's URL.

### read_webpage

Extract full content from a URL.

```
run({ skill: "exa", tool: "read_webpage", params: { url: "https://example.com" } })
```

## Auth

Exa uses NextAuth.js with an email verification code flow. Signup and signin are the same endpoint — NextAuth creates the account if it doesn't exist.

### Architecture

| Surface | Domain | Purpose |
|---------|--------|---------|
| Auth | `auth.exa.ai` | NextAuth.js — handles login, CSRF, email verification |
| Dashboard | `dashboard.exa.ai` | API key management, billing, usage |
| API | `api.exa.ai` | Search and content extraction (API key auth) |

### Login flow (email verification code)

```
1. GET  auth.exa.ai/api/auth/csrf           → csrfToken + __Host-next-auth.csrf-token cookie
2. POST auth.exa.ai/api/auth/signin/email   → { email, csrfToken, callbackUrl, json: "true" }
                                               → Exa sends 6-digit code to the email address
3. Retrieve code from email                  → Subject: "Sign in to Exa Dashboard"
                                               Body: "Your verification code for Exa is: XXXXXX"
4. GET  auth.exa.ai/api/auth/callback/email  → { token: CODE, email, callbackUrl }
                                               → Sets next-auth.session-token cookie on .exa.ai
5. GET  dashboard.exa.ai/api/auth/session    → Confirms session, returns user/team data
```

### Session cookie

The session is a JWT stored in `next-auth.session-token` on `.exa.ai`:
- HttpOnly, Secure, SameSite=Lax
- ~30 day expiry
- Cloudflare `cf_clearance` cookie also present (may require browser for initial acquisition)

### Dashboard API endpoints (cookie-authenticated)

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/auth/session` | GET | `{ user: { email, id, currentTeamId, hasCompletedNewAiOnboarding, teams }, expires }` |
| `/api/get-api-keys` | GET | `{ apiKeys: [{ id, name, enabled, createdAt, rateLimit }] }` — **`id` IS the full API key** (UI masks it, API doesn't) |
| `/api/get-teams` | GET | `{ teams: [{ id, name, role, totalAppliedCreditsCents, usageLimit }] }` |
| `/api/get-websets-billing` | GET | `{ hasAccess: bool }` |

### Auth operations (agent-orchestrated, Playwright for code submission)

The login is agent-orchestrated. HTTPX triggers the email, but the code submission requires Playwright because the auth page uses a native HTML form POST that HTTPX cannot replay (tested: both GET and POST to `/api/auth/callback/email` fail).

```
# Step 1: trigger the verification code email (HTTPX)
run({ skill: "exa", tool: "send_login_code", params: { email: "joe@contini.co" } })
# → { status: "code_sent", email, hint }

# Step 2: agent checks email (any provider)
# Look for subject "Sign in to Exa Dashboard", extract 6-digit code

# Step 3: Playwright login (native form POST)
run({ skill: "playwright", tool: "get_webpage", params: { url: "https://dashboard.exa.ai", wait_until: "domcontentloaded" } })
run({ skill: "playwright", tool: "type", params: { selector: "input[type=email]", text: "joe@contini.co" } })
run({ skill: "playwright", tool: "click", params: { selector: "button[type=submit]" } })
# Wait for code entry page...
run({ skill: "playwright", tool: "type", params: { selector: "input[placeholder='Enter verification code']", text: "CODE" } })
run({ skill: "playwright", tool: "click", params: { selector: "button[type=submit]" } })

# Step 4: extract cookies from browser
run({ skill: "playwright", tool: "cookies", params: { domain: ".exa.ai" } })
# → find next-auth.session-token and cf_clearance

# Step 5: store the session (HTTPX validates + stores via __secrets__)
run({ skill: "exa", tool: "store_session_cookies", params: {
  email: "joe@contini.co",
  session_token: "eyJhbG...",
  cf_clearance: "NIvx..."
} })

# Now dashboard operations work:
run({ skill: "exa", tool: "get_api_keys" })
run({ skill: "exa", tool: "get_teams" })
run({ skill: "exa", tool: "create_api_key", params: { name: "my-key" } })
```

### Playwright discovery notes

Discovered 2026-03-21/22 via Playwright interactive sessions:

- `fill` does NOT trigger React synthetic events on the login form — use `type` (real keystrokes) or the submit button stays disabled
- The login page has a hidden honeypot field: `input[name="website"][type="text"]`
- The verification code input: `input[placeholder='Enter verification code']` — maxLength 6, pattern `\d{6}`, no name/id attribute
- After first login, Exa gates navigation to `/onboarding` when `hasCompletedNewAiOnboarding: false` — skip or complete before accessing `/api-keys`
- The code submission is a **native HTML form POST** — fetch interceptor doesn't capture it, and HTTPX replay of `/api/auth/callback/email` fails with `?error=Verification` (GET) or `?error=configuration` (POST)
- Navigate to `https://dashboard.exa.ai` (not `auth.exa.ai` directly) — the auth page rejects direct access with "accessed incorrectly"
- Three auth providers available: `workos`, `google`, `email` (from `/api/auth/providers`)

### Key discovery

The `id` field in `GET /api/get-api-keys` is the full API key value in UUID format (e.g. `5bcbb3da-e415-44f1-8e57-10e92177f378`). The dashboard UI shows it masked (`5bcbb3******...`), but the API returns it unmasked. This means `get_api_keys` can extract and store keys directly — no need to capture them at creation time.

### Dashboard API endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /api/auth/session` | User info, team memberships |
| `GET /api/get-api-keys` | API keys with **full values** in `id` field |
| `GET /api/get-teams` | Rate limits, credits, usage, billing info |
| `GET /api/service-api-keys?teamId=` | Service API keys (separate from regular keys) |
| `GET /api/get-websets-billing` | Websets access flag |

### Open items

- `create_api_key`: exact POST endpoint not yet captured. Low priority since `get_api_keys` returns full key values.
- Google SSO path: not yet reverse-engineered (email code flow works for now)
- WorkOS SSO: available as a provider, not yet investigated

### Next steps

The current flow requires the agent to orchestrate Playwright for the code submission step (Option A). HTTPX can trigger the email and validate the session, but it cannot replay the native form POST. Future improvements:

- **Session-scoped state (Option B):** Temporary auth state stored in the MCP/agent session — like browser cookies but for the agent. Python writes to session storage in step 1, reads it back in step 2, without the agent shuttling opaque tokens.
- **`__needs__` continuation pattern:** Python yields a dependency declaration ("I need a verification code from email") and the engine fulfills it — pausing the operation, dispatching to the agent, and resuming when the dependency is met. This would collapse the multi-step flow into a single operation call.
- **Playwright-as-fallback for auth:** Formalize the pattern where HTTPX handles the happy path (send email, validate session, call APIs) and Playwright handles steps that require native browser behavior (form POSTs, captchas, SSO). The agent decides when to use which.

Both session state and `__needs__` are tracked on the engine roadmap under "Session-scoped state for auth flows."

## Known Limitations

**`read_webpage`**: May fail for URLs the crawl API cannot fetch (e.g., pages behind auth, rate-limited sites). The API returns empty results with error info in `statuses`. Retry with another integration that implements `webpage.read` using a real browser if you need JS rendering.
