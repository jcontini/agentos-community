# Python SDK

The agentOS Python SDK gives skills two functions: `molt` and `surf`.

```python
from agentos import molt, surf
```

That's the whole SDK. `molt` cleans and parses scraped data. `surf` makes HTTP requests that get past bot detection. Both are designed to work identically across future TypeScript, Go, and Rust SDKs.

---

## `molt` — shed the outer layer

Like a lobster shedding its shell, `molt` strips away the messy outer layer of scraped data and reveals the clean value underneath.

### Clean text (default)

```python
molt('<b>Hello</b> world')           # → 'Hello world'
molt('  Joe   Contini  ')            # → 'Joe Contini'
molt("hasn't added any details yet") # → None (sentinel)
molt('')                              # → None
molt(None)                            # → None
```

With no type argument, `molt` does three things in order:
1. **Strips HTML** — removes tags, decodes entities (`&amp;` → `&`)
2. **Normalizes whitespace** — collapses runs of spaces/tabs/newlines to single spaces
3. **Detects sentinels** — returns `None` for placeholder strings like "N/A", "unknown", "hasn't added any details yet"

### Parse to a type

Pass a target type as the second argument:

```python
molt('1,234 reviews', int)           # → 1234
molt('2.5K', int)                    # → 2500
molt('4.5 out of 5', float)          # → 4.5
molt('August 2010', 'date')          # → '2010-08'
molt('December 13, 2024', 'date')    # → '2024-12-13'
molt('in January 2026', 'date')      # → '2026-01'
molt(1616025600000, 'date')          # → '2021-03-18T...' (ms timestamp)
```

Type arguments: `int`, `float`, `'date'`, `str`. Use Python types or strings — both work, so the API translates to any language.

### When to use specific functions instead

`molt` handles 95% of cases. For fine-grained control:

| Function | When to use |
|----------|-------------|
| `clean_html(s)` | Preserve paragraph structure (`<br>` → newline, `</p>` → double newline) |
| `clean_sentinel(s)` | Only check for placeholders, no HTML stripping |
| `clean_text(s)` | Only normalize whitespace + decode entities, no HTML stripping or sentinel check |
| `parse_int(s)` | Parse integer without cleaning first |
| `parse_date(s)` | Parse date without cleaning first |

```python
from agentos import clean_html

# When you need paragraph breaks preserved (bios, descriptions)
bio = clean_html('<p>First paragraph.</p><p>Second paragraph.</p>')
# → 'First paragraph.\n\nSecond paragraph.'
```

---

## `surf` — ride through WAFs

`surf` creates an [httpx](https://www.python-httpx.org/) client pre-configured with browser-like headers, HTTP/2, cookie jar handling, and anti-bot profiles.

### Basic usage

```python
from agentos import surf

with surf() as s:
    resp = s.get('https://example.com/api/data')
    data = resp.json()
```

### With cookies (authenticated operations)

```python
from agentos import surf, get_cookies

def my_operation(params=None):
    cookie_header = get_cookies(params)
    with surf(cookies=cookie_header) as s:
        resp = s.get('https://example.com/account')
```

`get_cookies(params)` extracts the cookie header from the runtime params dict that agentOS injects into Python operations.

### Profiles

Different services have different anti-bot measures. `surf` has three header profiles, from lightest to heaviest:

| Profile | Headers | Use when |
|---------|---------|----------|
| `"default"` | User-Agent, Accept, Accept-Language | Most APIs, unprotected endpoints |
| `"api"` | + Sec-CH-UA, Sec-Fetch-* (CORS mode) | Cloudflare/CloudFront-protected JSON APIs |
| `"navigate"` | + Device-Memory, Downlink, Rtt, Ect, Dpr, full client hints | Protected HTML pages (Amazon, eBay, auth-gated content) |

```python
# CDN-protected API
with surf(cookies=header, profile="api") as s:
    resp = s.get('https://api.example.com/data')

# Amazon-level anti-bot (Lightsaber, Siege)
with surf(cookies=header, profile="navigate") as s:
    resp = s.get('https://www.amazon.com/your-orders/orders')
```

Start with the default. If you get 403/429, try `"api"`, then `"navigate"`. See [Transport & Anti-Bot](../reverse-engineering/1-transport/index.md) for the full diagnostic protocol.

### Cookie filtering

Some sites inject cookies that trigger client-side features (encryption, telemetry) that break HTTPX scraping. Strip them:

```python
with surf(cookies=header, skip_cookies={"csd-key", "csm-hit"}) as s:
    resp = s.get(url)  # server falls back to plain HTML
```

Amazon's `csd-key` cookie triggers Siege client-side encryption. Stripping it makes the server return readable HTML instead of encrypted blobs. See [Cookie Stripping](../reverse-engineering/1-transport/index.md#cookie-stripping--disabling-client-side-features).

### HTTP/2 toggle

Most services need HTTP/2 (default). Vercel Security Checkpoint blocks it:

```python
# Vercel-hosted endpoint that blocks h2
with surf(http2=False) as s:
    resp = s.get('https://dashboard.example.com')
```

### Extra headers

Merge additional headers with the profile defaults:

```python
with surf(cookies=header, profile="navigate", headers={"Host": "www.amazon.com"}) as s:
    resp = s.get(url)
```

---

## Cross-language API

The SDK is designed so the same concepts translate directly:

| Python | TypeScript | Go |
|--------|-----------|-----|
| `molt(s)` | `molt(s)` | `sdk.Molt(s)` |
| `molt(s, int)` | `molt(s, 'int')` | `sdk.Molt(s, sdk.Int)` |
| `molt(s, 'date')` | `molt(s, 'date')` | `sdk.Molt(s, sdk.Date)` |
| `surf(opts)` | `surf(opts)` | `sdk.Surf(opts)` |

---

## Quick reference

```python
from agentos import molt, surf, get_cookies

# --- molt: clean + parse ---
molt(s)                          # clean string
molt(s, int)                     # parse integer
molt(s, float)                   # parse float
molt(s, 'date')                  # parse to ISO 8601
molt(timestamp, 'date')          # convert ms/s timestamp

# --- surf: HTTP client ---
surf()                           # default browser headers
surf(cookies=header)             # with session cookies
surf(profile="navigate")         # full anti-bot headers
surf(skip_cookies={"csd-key"})   # strip trigger cookies
surf(http2=False)                # for Vercel endpoints
get_cookies(params)              # extract cookies from runtime params
```
