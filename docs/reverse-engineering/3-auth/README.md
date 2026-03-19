# Reverse Engineering — Auth & Runtime Config

How to get credentials, handle rotating config, and manage authentication for
reverse-engineered web skills.

This is Layer 3 of the reverse-engineering docs:

- **Layer 1: Transport** — [1-transport](../1-transport/)
- **Layer 2: Discovery** — [2-discovery](../2-discovery/)
- **Layer 3: Auth & Runtime** (this file) — credentials, sessions, rotating config
  - [workos.md](./workos.md) — WorkOS/Supabase migration pattern, JWT decoding, token refresh
- **Layer 4: Content** — [4-content](../4-content/) — HTML scraping when there is no API
- **Layer 5: Social Networks** — [5-social](../5-social/) — modeling people, relationships, and social graphs
- **Layer 6: Desktop Apps** — [6-desktop-apps](../6-desktop-apps/) — macOS, Electron, local state, unofficial APIs

---

## Cache + Discovery + Fallback Architecture

API keys and endpoints can rotate when the target site deploys. A resilient skill
needs a multi-tier discovery strategy that self-heals without human intervention.

### The three-tier pattern

```
Tier 1: Local file cache     (instant, usually works)
  |
  v  (cache miss or expired TTL)
Tier 2: Static extraction     (fast, ~1-2 seconds)
  |
  v  (site restructured, regex broke)
Tier 3: Headless browser      (slow, ~10-15 seconds, always works)
  |
  v  (browser also fails — site is down or completely redesigned)
Tier 4: Hardcoded fallback    (zero latency, may be stale)
```

### Implementation pattern

```python
import json, os, time

CACHE_PATH = os.path.join(os.path.dirname(__file__), ".runtime-cache.json")
CACHE_TTL = 86400  # 24 hours

def _load_cache() -> dict | None:
    """Tier 1: return cached config if fresh."""
    try:
        with open(CACHE_PATH) as f:
            cached = json.load(f)
        if time.time() - cached.get("ts", 0) < CACHE_TTL:
            return cached
    except (OSError, json.JSONDecodeError):
        pass
    return None

def _save_cache(config: dict):
    config["ts"] = time.time()
    with open(CACHE_PATH, "w") as f:
        json.dump(config, f)

def discover_runtime(**kwargs) -> dict:
    """Multi-tier runtime discovery."""
    cached = _load_cache()
    if cached:
        return cached

    # Tier 2: extract from JS bundle (fast, no browser needed)
    config = discover_from_bundle(kwargs.get("html_text"))
    if config:
        _save_cache(config)
        return config

    # Tier 3: headless browser capture (slow but reliable)
    config = discover_via_browser(kwargs.get("page_url"))
    if config:
        _save_cache(config)
        return config

    # Tier 4: hardcoded fallback
    return {"endpoint": FALLBACK_ENDPOINT, "api_key": FALLBACK_API_KEY}
```

### When to use each tier

| Tier | Speed | Reliability | When it fails |
|---|---|---|---|
| File cache | ~0ms | High (within TTL) | First run, or config rotated since last cache |
| JS bundle extraction | 1-2s | Medium | Site changes bundle structure, obfuscation changes |
| Headless browser capture | 10-15s | High | Site deploys new bot detection, browser not available |
| Hardcoded fallback | ~0ms | Low (degrades over time) | API key rotated since skill was last updated |

### Cache management

> **Update:** File-based caching (`.runtime-cache.json`) has been replaced by
> sandbox storage — the executor reads/writes `cache` vals on the skill's graph
> node. See `spec/sandbox-storage.md` for details.

The cache stores the discovered endpoint and API key. Sandbox storage persists
across restarts and can be cleared via the standard "clear cache" action.

### Real example

See `skills/goodreads/public_graph.py` `discover_runtime()` for a full
implementation of all four tiers against Goodreads' AppSync GraphQL backend,
using sandbox storage for the cache tier.

---

## Cookie-Based Session Auth

For sites that require login but use session cookies (not JWTs), the pattern is:
use Playwright once to log in, extract the cookies, then reuse them in `httpx`
or `urllib` for all subsequent API calls.

### Pattern

```python
from playwright.sync_api import sync_playwright

def extract_session_cookies(login_url: str, email: str, password: str) -> dict:
    """Log in via Playwright and return session cookies."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
        )
        page = context.new_page()
        page.goto(login_url)

        # Fill login form
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')

        # Wait for redirect / auth completion
        page.wait_for_url("**/dashboard**", timeout=15000)

        # Extract cookies
        cookies = {c["name"]: c["value"] for c in context.cookies()}
        browser.close()
    return cookies
```

### Reusing cookies in httpx

```python
cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
headers = {"Cookie": cookie_header, **STANDARD_HEADERS}
resp = httpx.get(api_url, headers=headers)
```

### Cookie storage in agentOS

agentOS resolves cookies from the user's local browser profiles (`firefox`,
`brave-browser`, `chrome`, etc.). For operations that need session auth, omit
`auth: none` in the skill descriptor and let the runtime handle cookie resolution.

For operations that are public and do NOT need cookies, explicitly declare
`auth: none` per-operation to avoid triggering the cookie resolver:

```yaml
operations:
  search_books:
    auth: none    # public API, no session needed
    method: GET
    url: ...
```

### Real example

See `skills/claude/claude-login.py` for Playwright-based cookie extraction from
`claude.ai` (Cloudflare-protected, requires full stealth settings).

---

## AWS Cognito Auth

Common in gym/fitness SaaS apps (approach.app, Mindbody, etc.). Cognito endpoints
are pure AWS API calls — no browser headers needed.

### Login pattern

```python
import json, httpx

def cognito_login(email: str, password: str, client_id: str) -> dict:
    """Returns AccessToken, IdToken, RefreshToken."""
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
    resp.raise_for_status()
    return resp.json()["AuthenticationResult"]
```

### Finding Cognito credentials

The `ClientId` and `UserPoolId` are embedded in the app's JS bundle. Search for:

- `userPoolId` — format: `us-east-1_XXXXXXXXX`
- `userPoolClientId` — format: 26-character alphanumeric string
- `userPoolWebClientId` — same as above, sometimes different key name

These are usually grouped together in the bundle near other AWS config.

### Token usage

After login, use the `AccessToken` as a `Bearer` token:

```python
headers = {"Authorization": f"Bearer {tokens['AccessToken']}"}
```

Or the `IdToken` depending on which the API expects (check the bundle's interceptor).

---

## Multi-Environment Config Selection

Production bundles often ship configs for all environments. You need to pick the
right one (Prod) to avoid hitting dev/staging endpoints that may behave differently
or be behind VPN.

### How to identify Prod

| Signal | Example |
|---|---|
| `shortName` or `envName` field | `"shortName": "Prod"` |
| Ads enabled | `"showAds": true` (dev/staging usually has this off) |
| Analytics enabled | `"publishWebVitalMetrics": true` |
| Domain patterns | Production AppSync endpoints often have different subdomain prefixes |
| Last in the array | Webpack build order often puts Prod last |

### Extraction pattern

```python
import re, json

def extract_prod_config(bundle_js: str) -> dict | None:
    """Find the Prod environment config from a multi-env JS bundle."""
    pattern = re.compile(
        r'\{[^{}]*"graphql"\s*:\s*\{[^{}]*"apiKey"\s*:\s*"[^"]+[^{}]*\}[^{}]*"shortName"\s*:\s*"([^"]+)"[^{}]*\}'
    )
    for match in pattern.finditer(bundle_js):
        if match.group(1) == "Prod":
            return json.loads(match.group(0))
    return None
```

### Real example: Goodreads

Goodreads ships Dev, Beta, Preprod, and Prod AppSync configs in their `_app` chunk.
The Prod config is identified by `"shortName": "Prod"` and `"showAds": true`.
See `skills/goodreads/public_graph.py` `discover_from_bundle()`.

---

## Auth Boundary Taxonomy

Different operations within the same skill may have different auth requirements.
Classify each operation during reverse engineering.

### Three tiers

| Tier | Description | Example |
|---|---|---|
| **Public** | Works anonymously with just the frontend API key | Goodreads `getSearchSuggestions`, `getReviews`, `getSimilarBooks` |
| **Suggested auth** | Returns data either way, but richer results with a session | Goodreads reviews with `viewerHasLiked` field |
| **Required auth** | Fails without user session context | Goodreads `getUser`, `getEditions`; mutations like `RateBook`, `ShelveBook` |

### Mapping technique

1. Discover all operations from JS bundles (see [discovery doc](2-discovery.md#graphql-schema-discovery-via-js-bundles))
2. For each operation, send a request with only the public API key
3. Classify the response using this table:

| Response | Classification |
|---|---|
| `200` with `data` fields populated | Public |
| `200` with `data` + some `errors` on specific fields | Suggested auth (field-level restrictions) |
| `200` with VTL/MappingTemplate error | Required auth |
| `401` / `403` at transport level | Required auth |

### Skill descriptor implications

```yaml
operations:
  # Public operation — no cookies needed
  search_books:
    auth: none
    method: POST
    url: "{{graphql_endpoint}}"

  # Auth required — let agentOS resolve cookies
  rate_book:
    method: POST
    url: "{{graphql_endpoint}}"
    # No auth: none → agentOS will resolve session cookies
```

Operations without `auth: none` will trigger agentOS cookie resolution. If a user
has multiple browser profiles, agentOS will ask which one to use.

---

## Real-World Examples in This Repo

| Skill | Auth pattern | Reference |
|---|---|---|
| `skills/goodreads/` | Multi-tier cache+discovery+fallback for AppSync API key; public/auth boundary mapping | `public_graph.py` |
| `skills/claude/` | Playwright cookie extraction from Cloudflare-protected login | `claude-login.py` |
| `skills/austin-boulder-project/` | Bundle-extracted API key + namespace-as-Authorization | `abp.py` |
