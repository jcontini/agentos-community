# Reverse Engineering — Transport & Anti-Bot

How to get a response from a server that doesn't want to talk to you.

This is Layer 1 of the reverse-engineering docs:

- **Layer 1: Transport** (this file) — TLS fingerprinting, headers, WAF bypass, headless stealth
- **Layer 2: Discovery** — [2-discovery](../2-discovery/index.md) — finding structured data in pages and bundles
- **Layer 3: Auth & Runtime** — [3-auth](../3-auth/index.md) — credentials, sessions, rotating config
- **Layer 4: Content** — [4-content](../4-content/index.md) — extracting data from HTML when there is no API
- **Layer 5: Social Networks** — [5-social](../5-social/index.md) — modeling people, relationships, and social graphs
- **Layer 6: Desktop Apps** — [6-desktop-apps](../6-desktop-apps/index.md) — macOS, Electron, local state, unofficial APIs
- **Layer 7: MCP Servers** — [7-mcp](../7-mcp/index.md) — discovering, probing, and evaluating remote/stdio MCPs

---

## HTTP Client — Always `httpx`, But Not Always `http2=True`

### The short answer

```python
import httpx

# Default — works for most APIs (CloudFront, Cloudflare CDN, unprotected)
with httpx.Client(http2=True, follow_redirects=True, timeout=30) as client:
    resp = client.get(url, headers=headers)
    resp.raise_for_status()
```

### Why `requests` fails against modern CDNs

`requests` (backed by `urllib3`) only advertises `http/1.1` in its TLS ALPN extension.
Modern CDNs including **AWS CloudFront** and **Cloudflare** use **JA4 fingerprinting**,
which includes the ALPN value as a primary field. Since ~98% of real browser traffic
is HTTP/2+, an `ALPN=http/1.1` client is immediately flagged as a bot.

`httpx` with `http2=True` advertises `["h2", "http/1.1"]`, producing a JA4 fingerprint
that matches browsers and passes WAF checks.

Additionally, `requests`/urllib3 has a well-known, publicly blocklisted JA3 hash
(`8d9f7747675e24454cd9b7ed35c58707`) — many WAFs block this hash outright.

**AWS WAF added JA4 fingerprinting in March 2025.** If you're seeing `400` or `403`
from a CloudFront-fronted API that works fine in the browser, TLS fingerprinting is
the most likely cause.

### When to use `http2=False`

**Vercel Security Checkpoint** blocks `httpx(http2=True)` outright — every request
returns `429` with a JS challenge page, regardless of cookies or headers. But
`httpx(http2=False)` passes cleanly, no cookies or special headers needed.

This is the opposite of the CloudFront pattern and the reason is JA4 fingerprint
specificity. HTTP/2 ALPN + httpx's cipher suite ordering produce a distinctive,
well-known bot fingerprint that Vercel blocks. HTTP/1.1 has a much smaller
fingerprint surface — fewer signals to distinguish httpx from a legitimate app,
so Vercel lets it through.

Not every Vercel-hosted endpoint enables the checkpoint. During Exa testing,
`auth.exa.ai` (Vercel, no checkpoint) accepted h2; `dashboard.exa.ai`
(Vercel, checkpoint enabled) rejected it. The checkpoint is a per-project
Vercel Firewall setting — you have to test each subdomain.

**Tested against `dashboard.exa.ai` (Vercel + Cloudflare):**

| | `http2=True` | `http2=False` |
|---|---|---|
| session + cf_clearance | 429 | 200 |
| session only | 429 | 200 |
| no cookies at all | 429 | 200 (empty session) |

Cookies and headers are irrelevant — the checkpoint triggers purely on
the HTTP/2 TLS fingerprint.

**Rule of thumb:** start with `http2=True`. If you get `429` with "Vercel
Security Checkpoint" HTML, switch to `http2=False`. If you get `403`/`400`
from CloudFront, make sure you're on `http2=True`.

### Diagnostic protocol: isolating the variable

When a request fails, don't guess — isolate. Test each transport variable
independently to find the one that matters:

```
Step 1: Try httpx http2=True (default)
  → Works?     Done.
  → 429/403?   Continue.

Step 2: Try httpx http2=False
  → Works?     Vercel Security Checkpoint. Use http2=False, done.
  → Still 403? Continue.

Step 3: Try with full browser-like headers (Sec-Fetch-*, Sec-CH-UA, etc.)
  → Works?     WAF header check. Add headers, done.
  → Still 403? Continue.

Step 4: Try with valid session cookies
  → Works?     Auth required. Handle login first.
  → Still 403? It's TLS fingerprint-level.

Step 5: Use curl_cffi with Chrome impersonation
  → Works?     Strict JA3/JA4 enforcement. Use curl_cffi.
  → Still 403? Something non-standard (CAPTCHA, IP block).
```

The key insight from the Exa reverse engineering session: **test one variable
at a time.** During Exa testing, we created a matrix of `http2=True/False` x
`cookies/no-cookies` x `headers/no-headers` and discovered that ONLY the h2
setting mattered. Cookies and headers were completely irrelevant to the
Vercel checkpoint. This prevented unnecessary complexity in the skill code.

### If `httpx` isn't enough

For the strictest Cloudflare Bot Management (Akamai-level h2 frame fingerprinting):

```python
from curl_cffi import requests as cffi_requests

resp = cffi_requests.get(url, impersonate="chrome124", headers=headers)
```

`curl_cffi` emits Chrome's exact TLS cipher suites, GREASE values, extension ordering,
ALPN, and HTTP/2 `SETTINGS` frames — the full fingerprint. Use this as the nuclear option.

### Installation

```bash
pip install "httpx[http2]"     # for httpx + HTTP/2 support
pip install curl_cffi           # for full Chrome fingerprint impersonation (rarely needed)
```

### When `urllib` is acceptable

Python's built-in `urllib.request` works for sites that don't use CDN-level bot
detection — plain origin servers, AWS AppSync endpoints, and APIs behind API Gateway
without WAF rules. The Goodreads skill uses `urllib` successfully because its AppSync
endpoint doesn't enforce TLS fingerprinting. Prefer `httpx` by default, but `urllib`
is fine when you've confirmed the target doesn't care.

---

## Browser-Like Headers

Even with the right HTTP client, most CDN-protected APIs also check headers.
Always send the full set that a real browser XHR would produce:

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",  # client must handle decompression
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",   # or "same-origin" / "same-site" as appropriate
    "Origin": "https://app.example.com",
    "Referer": "https://app.example.com/",
}
```

**`Sec-Fetch-*` headers are especially important for Cloudflare.** The Claude skill on
`claude.ai` (which is Cloudflare-protected) requires `Sec-Fetch-Site: same-origin` to
bypass its bot check. Without them, you get `403` even with a valid session cookie.

### Choosing `Sec-Fetch-Site`

| Scenario | Value |
|---|---|
| JS on `app.example.com` calling `app.example.com/api` | `same-origin` |
| JS on `app.example.com` calling `api.example.com` | `same-site` |
| JS on `portal.approach.app` calling `widgets.tilefive.com` | `cross-site` |

### Client Hints — Beyond the Basics

Some services go further than `Sec-CH-UA` and check for the full set of
**client hints** that a real browser navigation produces. Amazon's bot detection
(Lightsaber) is a prime example — it validates `Device-Memory`, `Downlink`, `Rtt`,
and other hints that most scraping guides don't mention.

**Full client hints header set (for page navigations):**

```python
AUTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,...",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",  # MUST match client decompression capability
    "Cache-Control": "max-age=0",
    # --- Network quality hints ---
    "Device-Memory": "8",
    "Downlink": "10",
    "Dpr": "2",
    "Ect": "4g",
    "Rtt": "50",
    # --- Structured client hints ---
    "Sec-Ch-Device-Memory": "8",
    "Sec-Ch-Dpr": "2",
    "Sec-Ch-Ua": '"Chromium";v="145", "Not:A-Brand";v="99"',
    "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="145.0.7632.6", "Not:A-Brand";v="99.0.0.0"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Ch-Viewport-Width": "1512",
    # --- Navigation fetch metadata ---
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Viewport-Width": "1512",
}
```

The critical ones most people miss: `Device-Memory`, `Rtt`, `Downlink`, `Ect`,
`Dpr`, and `Sec-Ch-Ua-Full-Version-List`. These are sent by Chrome on every
navigation and fingerprinted by Amazon, eBay, and other major retailers.

**When to use which set:**

| Request type | Headers needed |
|---|---|
| XHR / `fetch()` API calls | Basic set (`Sec-CH-UA`, `Sec-Fetch-*: cors`) |
| Full page navigation | Full set with client hints, `Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate` |
| Authenticated HTML pages | Full set — stricter bot detection on auth-gated content |

**How to discover the right headers:** Use the Playwright skill's
`capture_network` or the fetch interceptor to see exactly what headers a real
browser sends on the same request. Copy them into your skill and test one at a
time to find which ones matter. See `skills/amazon/amazon.py` `AUTH_HEADERS`
for a complete real-world example.

### Version drift

Pin `Sec-Ch-Ua` and `Sec-Ch-Ua-Full-Version-List` to a current Chrome version.
If you start getting unexpected 403s or redirects months later, the pinned
version may be too old. Update it to match the current stable Chrome release.

---

## Cookie Stripping — Disabling Client-Side Features

Some sites inject JavaScript-driven features via cookies. When you're scraping
with HTTPX (no JS engine), these features produce unusable output. The fix:
**strip the trigger cookies** so the server falls back to plain HTML.

### Amazon's Siege Encryption

Amazon uses a system called `SiegeClientSideDecryption` to encrypt page content
client-side. When the `csd-key` cookie is present, Amazon sends encrypted HTML
blobs instead of readable content. The browser decrypts them with JavaScript;
HTTPX gets unreadable garbage.

**Solution:** strip the trigger cookies before sending requests:

```python
SKIP_COOKIES = {"csd-key", "csm-hit", "aws-waf-token"}

def _auth_client(cookie_header: str) -> httpx.Client:
    cookies = {
        k: v for k, v in _parse_cookie_header(cookie_header).items()
        if k not in SKIP_COOKIES
    }
    return httpx.Client(http2=True, cookies=cookies, ...)
```

With `csd-key` stripped, Amazon serves plain, parseable HTML. The `csm-hit` and
`aws-waf-token` cookies are also stripped — they're telemetry/WAF cookies that
can trigger additional client-side behavior.

### Diagnosing encryption

If your HTML responses contain garbled content, long base64 strings, or empty
containers where data should be, check for client-side decryption:

1. Compare the page source in the browser (View Source, not DevTools Elements)
   with your HTTPX response
2. Search for keywords like `decrypt`, `Siege`, `clientSide` in the page JS
3. Try stripping cookies one at a time to find which one triggers encryption

Reference: `skills/amazon/amazon.py` `SKIP_COOKIES`.

---

## Response Decompression — You Must Handle What You Advertise

When you send `Accept-Encoding: gzip, deflate, br, zstd` (as all browser-like profiles do), the server will compress its response. **Your HTTP client must decompress it.** If it doesn't, you get raw binary garbage instead of HTML — and every parser returns zero results.

This is a silent failure. The HTTP status is 200, the headers look normal, and `Content-Length` is reasonable. But `resp.text` is garbled bytes. It looks like client-side encryption (see above), but the cause is much simpler: the response is compressed and you're not decompressing it.

### How `agentos.http` handles it

The Rust HTTP engine uses reqwest with `gzip`, `brotli`, `deflate`, and `zstd` feature flags enabled. Decompression is automatic and transparent — `resp["body"]` is always plaintext.

### Why this matters

**Brotli** (RFC 7932) is a compression algorithm designed by Google for the web. It compresses 20-26% better than gzip on HTML/CSS/JS. Every modern browser supports it, and servers aggressively use it for large pages. Amazon's order history page, for example, returns ~168KB of brotli-compressed HTML. Without decompression, you get 168KB of binary noise and zero order cards.

**The trap:** small pages (homepages, API endpoints) may not be compressed or may use gzip which some clients handle by default. Large pages (order history, dashboards, search results) almost always use brotli. So your skill works on simple endpoints and silently fails on the important ones.

### Diagnostic

If your response body contains non-UTF-8 bytes, starts with garbled characters, or contains no recognizable HTML despite a 200 status:

1. Check the response `Content-Encoding` header — if it says `br`, `gzip`, or `zstd`, the body is compressed
2. Verify your HTTP client has decompression enabled
3. In agentOS: `agentos.http` handles this automatically. If you're using raw `urllib.request`, it does NOT decompress brotli

Reference: `Cargo.toml` reqwest features — `gzip`, `brotli`, `deflate`, `zstd`.

---

## Session Warming

Some services track request patterns and flag direct deep-links from an unknown
session as bot traffic. The fix: **warm the session** by visiting the homepage
first, then navigate to the target page.

```python
def _warm_session(client: httpx.Client) -> None:
    client.get("https://www.amazon.com", headers={"Sec-Fetch-Site": "none"})
    time.sleep(1.0)
```

This establishes the session context (cookies, CSRF tokens, tracking state)
before hitting authenticated pages. Without it, Amazon redirects order history
and account pages to the login page even with valid session cookies.

**When to warm:**
- Before any authenticated page fetch (order history, account settings)
- When the first request to a deep URL returns a login redirect despite valid cookies
- When you see WAF-level blocks only on direct navigation

**When warming isn't needed:**
- API endpoints (JSON responses) — they don't use page-level session tracking
- Public pages without authentication
- Sites where direct deep-links work fine (test first)

Reference: `skills/amazon/amazon.py` `_warm_session()`.

---

## Headless Browser Stealth

Default Playwright/Chromium gets blocked by many sites (Goodreads returns 403,
Cloudflare serves challenge pages). The fix is a set of anti-fingerprinting settings.

### Minimum stealth settings

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1440, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
    """)
```

### What each setting does

| Setting | Why |
|---|---|
| `--disable-blink-features=AutomationControlled` | Removes the `navigator.webdriver=true` flag that Chromium sets in automation mode |
| Custom `user_agent` | Default headless UA contains `HeadlessChrome` which is trivially blocked |
| `viewport` | Default headless viewport is 800x600, which no real user has |
| `locale` / `timezone_id` | Some bot detectors check for mismatches between locale and timezone |
| `navigator.webdriver = false` | Belt-and-suspenders override in case the flag leaks through other paths |

### Real example: Goodreads

Default Playwright against `goodreads.com/book/show/4934` returns HTTP 403 with
one network request. With stealth settings, the page loads fully with 1400+ requests
including 4 AppSync GraphQL calls. See `skills/goodreads/public_graph.py`
`discover_via_browser()` for the implementation.

---

## CDP Detection Signals — Why Playwright Gets Caught

Even with the stealth settings above, Playwright is still detectable at the
**Chrome DevTools Protocol (CDP) layer**. These signals are invisible in
DevTools and unrelated to headers, cookies, or user-agent strings. They matter
most during reverse engineering sessions — if a site behaves differently under
Playwright than in your real browser, CDP leaks are likely the cause.

### Runtime.Enable leak

Playwright calls `Runtime.Enable` on every CDP session to receive execution
context events. Anti-bot systems (Cloudflare, DataDome) detect this with a few
lines of in-page JavaScript that only fire when `Runtime.Enable` is active.
This is the single most devastating detection vector — it works regardless of
all other stealth measures.

### sourceURL leak

Playwright appends `//# sourceURL=__playwright_evaluation_script__` to every
`page.evaluate()` call. Any page script can inspect error stack traces and see
these telltale URLs. This means your `__NEXT_DATA__` extraction, DOM inspection,
or any other `evaluate()` call leaves a fingerprint.

### Utility world name

Playwright creates an isolated world named `__playwright_utility_world__` that
is visible in Chrome's internal state and potentially to detection scripts.

### What to do about it

These leaks are baked into Playwright's source code — no launch flag or init
script fixes them. Two options:

1. **For most RE work:** The stealth settings above (flags, UA, viewport,
   webdriver override) are enough. Most sites don't check CDP-level signals.
   If a site seems to behave differently under Playwright, check for these
   leaks before adding complexity.

2. **For strict sites (Cloudflare Bot Management, DataDome):** Use
   [`rebrowser-playwright`](https://github.com/rebrowser/rebrowser-patches)
   as a drop-in replacement. It patches Playwright's source to eliminate
   `Runtime.Enable` calls, randomize sourceURLs, and rename the utility
   world. Install: `npm install rebrowser-playwright` and change your import.

**This doesn't affect production skills.** Our architecture uses Playwright
only for discovery — production calls go through `surf()` / HTTPX, which has
zero CDP surface. The CDP leaks only matter during reverse engineering sessions
where you're using the browser to investigate a protected site.

---

## Standard `_fetch` Helper

Recommended reusable pattern for skill Python modules:

```python
import httpx
import time

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_BASE_HEADERS = {
    "User-Agent": _BROWSER_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",  # client must handle decompression
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}


def _fetch(url: str, *, headers: dict | None = None, data: bytes | None = None) -> bytes:
    """
    Fetch with httpx + HTTP/2 and retry on transient errors.

    httpx is required over requests/urllib — see docs/reverse-engineering/1-transport/.
    data=bytes -> POST, otherwise GET.
    """
    merged = dict(_BASE_HEADERS)
    if headers:
        merged.update(headers)
    method = "POST" if data is not None else "GET"
    last_err = None
    for attempt in range(3):
        try:
            with httpx.Client(http2=True, follow_redirects=True, timeout=30) as client:
                resp = client.request(method, url, headers=merged, content=data)
                resp.raise_for_status()
                return resp.content
        except httpx.HTTPStatusError as e:
            last_err = e
            if e.response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except Exception as e:
            last_err = e
            if attempt == 2:
                raise
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Request failed: {last_err}")
```

---

## Debugging 400/403 Errors

| Symptom | Likely cause | Fix |
|---|---|---|
| `403` from CloudFront with a bot-detection HTML page | JA3/JA4 fingerprint blocked | Switch to `httpx(http2=True)` |
| `400` from CloudFront, body is `"Forbidden"` or short string | WAF rule triggered (header order, ALPN) | `httpx(http2=True)` + `Sec-Fetch-*` headers |
| `400`, body looks like `"404"` | API Gateway can't route the request — usually a missing tenant/auth header | Find and add the missing header (check the bundle's axios factory) |
| `403` for a same-origin API (e.g. `claude.ai`) | Missing `Sec-Fetch-*` headers | Add `Sec-Fetch-Site: same-origin` + `Sec-Fetch-Mode: cors` + `Sec-Fetch-Dest: empty` |
| `403` from headless Playwright | Default Chromium automation fingerprint | Add stealth settings (see Headless Browser Stealth above) |
| `429` with "Vercel Security Checkpoint" HTML | Vercel blocks httpx's h2 fingerprint | Switch to `httpx(http2=False)` — cookies and headers don't matter, it's purely TLS |
| Works in browser, fails in Python regardless | Check for authorization that's not a JWT | Look for short `Authorization` values in the bundle (namespace, env name, etc.) |

### Using Playwright to capture exact headers

When you're stuck, use Playwright to intercept the actual XHR and log all headers
(including those added by axios interceptors that aren't visible in DevTools):

```python
from playwright.sync_api import sync_playwright

def capture_request_headers(url_pattern: str, trigger_url: str) -> dict:
    """Navigate to trigger_url and capture headers from the first request matching url_pattern."""
    captured = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("request", lambda req: captured.update(req.headers)
                if url_pattern in req.url else None)
        page.goto(trigger_url)
        page.wait_for_timeout(3000)
        browser.close()
    return captured
```

---

## Skill File Layout

```
skills/<skill-name>/
  readme.md            <- agentOS skill descriptor (operations, adapters, etc.)
  requirements.md      <- reverse engineering notes, API docs, findings log
  <skill>.py           <- Python module with all API functions
  icon.svg             <- skill icon
```

Keep `requirements.md` as a living document — update it every time you discover
a new endpoint, figure out a new header, or resolve a mystery.

---

## Real-World Examples in This Repo

| Skill | Service | Key transport learnings |
|---|---|---|
| `skills/amazon/` | Amazon (Lightsaber bot detection) | Full client hints required (`Device-Memory`, `Rtt`, `Downlink`, etc.), cookie stripping for Siege encryption bypass, session warming before deep-link navigation |
| `skills/austin-boulder-project/` | Tilefive / approach.app | `httpx(http2=True)` required for CloudFront, `Authorization` = namespace string |
| `skills/claude/` | claude.ai (Cloudflare) | `Sec-Fetch-*` headers required, `403` without them even with valid cookies |
| `skills/exa/` | dashboard.exa.ai (Vercel + Cloudflare) | `http2=False` bypasses Vercel Security Checkpoint — no cookies needed, h2 triggers 429 regardless. Full email login flow works with HTTPX alone. |
| `skills/goodreads/` | Goodreads / AppSync | `urllib` works for AppSync (no WAF), but headless Playwright needs full stealth settings |
