# Reverse Engineering — Transport & Anti-Bot

How to get a response from a server that doesn't want to talk to you.

This is Layer 1 of the reverse-engineering docs:

- **Layer 1: Transport** (this file) — TLS fingerprinting, headers, WAF bypass, headless stealth
- **Layer 2: Discovery** — [2-discovery](../2-discovery/README.md) — finding structured data in pages and bundles
- **Layer 3: Auth & Runtime** — [3-auth](../3-auth/README.md) — credentials, sessions, rotating config
- **Layer 4: Content** — [4-content](../4-content/README.md) — extracting data from HTML when there is no API
- **Layer 5: Social Networks** — [5-social](../5-social/README.md) — modeling people, relationships, and social graphs
- **Layer 6: Desktop Apps** — [6-desktop-apps](../6-desktop-apps/README.md) — macOS, Electron, local state, unofficial APIs
- **Layer 7: MCP Servers** — [7-mcp](../7-mcp/README.md) — discovering, probing, and evaluating remote/stdio MCPs

---

## HTTP Client — Always Use `httpx`, Never `requests`

### The short answer

```python
import httpx

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
pip install curl_cffi           # for full Chrome fingerprint impersonation
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
    "Accept-Encoding": "gzip, deflate, br",
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
    "Accept-Encoding": "gzip, deflate, br",
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
| `skills/austin-boulder-project/` | Tilefive / approach.app | `httpx(http2=True)` required for CloudFront, `Authorization` = namespace string |
| `skills/claude/` | claude.ai (Cloudflare) | `Sec-Fetch-*` headers required, `403` without them even with valid cookies |
| `skills/goodreads/` | Goodreads / AppSync | `urllib` works for AppSync (no WAF), but headless Playwright needs full stealth settings |
