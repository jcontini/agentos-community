# Python SDK

The agentOS SDK in three imports:

```python
from agentos import molt, http, shape
```

`molt` cleans and parses scraped data. `http` makes requests through the engine with composable header knobs for WAF bypass. `shape` gives you 60 typed entity classes. All three are designed to work identically across future TypeScript, Go, and Rust SDKs.

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
molt('4.5 out of 5', float)         # → 4.5
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

## `http` — all requests go through the engine

Every HTTP request routes through the Rust engine via dispatch. The engine handles transport (HTTP/2, decompression, timeouts), cookie jar management with automatic writeback, and request/response logging. Headers are built in Python via `http.headers()` — the engine sets zero default headers.

### Simple requests

```python
from agentos import http

resp = http.get('https://api.example.com/data')
data = resp["json"]

resp = http.post('https://api.example.com/items', json={"name": "thing"})
```

Response is always a dict: `{status, ok, url, headers, body, json}`. `json` is `None` if the response isn't JSON.

### With cookies (authenticated operations)

```python
from agentos import http, get_cookies

def my_operation(**params):
    cookie_header = get_cookies(params)
    resp = http.get('https://example.com/account', cookies=cookie_header)
```

`get_cookies(params)` extracts the cookie header from the runtime params dict that agentOS injects into Python operations.

### Sessions with cookie jar

For multi-request flows where cookies accumulate across requests:

```python
with http.client(cookies=cookie_header) as c:
    c.get("https://www.amazon.com/", **http.headers(waf="cf", mode="navigate", accept="html"))
    resp = c.get("https://www.amazon.com/gp/your-account/order-history",
                  **http.headers(waf="cf", mode="navigate", accept="html"))
    orders = resp["body"]
```

The engine tracks Set-Cookie responses and diffs the jar on close for automatic writeback to the credential store. Connection pools persist across requests within a session.

### `http.headers()` — composable header knobs

Headers are built from four independent knobs. The engine sets zero headers — Python controls everything.

```python
conf = http.headers(waf="cf", ua="chrome-desktop", mode="navigate", accept="html")
# Returns {"headers": {...}, "http2": True}
# Spread into http.get/post/client with **
```

| Knob | What it controls | Values |
|------|-----------------|--------|
| `waf` | WAF vendor — client hints + HTTP/2 | `"cf"` (CloudFront/Cloudflare), `"vercel"`, `None` |
| `ua` | User-Agent | `"chrome-desktop"`, `"chrome-mobile"`, `"safari-desktop"`, or raw string |
| `mode` | Sec-Fetch-* metadata (only when waf is set) | `"fetch"` (XHR), `"navigate"` (page load + device hints) |
| `accept` | Content negotiation | `"json"`, `"html"`, `"any"` (default) |
| `extra` | Custom headers merged last | Auth tokens, CSRF, Origin, Referer, etc. |

```python
# JSON API (Gmail, Linear, Todoist)
resp = http.get(url, **http.headers(accept="json", extra={"Authorization": f"Bearer {token}"}))

# HTML behind CloudFront (Amazon, Goodreads)
resp = http.get(url, **http.headers(waf="cf", mode="navigate", accept="html"))

# Vercel checkpoint bypass
resp = http.get(url, **http.headers(waf="vercel", accept="json"))
```

See [Transport & Anti-Bot](../reverse-engineering/1-transport/index.md) for the full diagnostic protocol.

### Cookie filtering

Some sites inject cookies that trigger client-side features (encryption, telemetry) that break scraping. Strip them:

```python
with http.client(cookies=header, skip_cookies=["csd-key", "csm-hit"]) as c:
    resp = c.get(url)  # server falls back to plain HTML
```

Amazon's `csd-key` cookie triggers Siege client-side encryption. Stripping it makes the server return readable HTML instead of encrypted blobs. See [Cookie Stripping](../reverse-engineering/1-transport/index.md#cookie-stripping--disabling-client-side-features).

### Extra headers

Custom headers go in the `extra=` parameter of `http.headers()`:

```python
with http.client(cookies=header,
                 **http.headers(waf="cf", mode="navigate", accept="html",
                                extra={"Host": "www.amazon.com"})) as c:
    resp = c.get(url)
```

---

## `shape` — typed entity schemas

60 entity types auto-generated from shape YAML definitions. One namespace, all types.

```python
from agentos import shape

book: shape.Book = {
    "id": "123",
    "name": "The Brothers Karamazov",
    "author": "Dostoevsky",
    "datePublished": "1880",
}

person: shape.Person = {
    "id": "456",
    "name": "Joe",
    "url": "https://goodreads.com/user/show/456",
}

post: shape.Post = {
    "id": "789",
    "name": "Show HN: agentOS",
    "author": "jcontini",
    "datePublished": "2026-03-26",
}
```

Every shape has standard fields (`id`, `name`, `text`, `url`, `image`, `author`, `datePublished`) plus shape-specific fields and relations. Shapes are defined in `shapes/*.yaml` and generated at build time.

Available shapes include: Account, Article, Author, Book, Community, Conversation, Domain, Email, Event, File, Flight, Meeting, Message, Note, Order, Person, Place, Playlist, Post, Product, Repository, Review, Role, Task, Transaction, Video, and more.

---

## Cross-language API

The SDK is designed so the same concepts translate directly:

| Python | TypeScript | Go |
|--------|-----------|-----|
| `molt(s)` | `molt(s)` | `sdk.Molt(s)` |
| `molt(s, int)` | `molt(s, 'int')` | `sdk.Molt(s, sdk.Int)` |
| `http.get(url)` | `http.get(url)` | `sdk.HTTP.Get(url)` |
| `shape.Book` | `shape.Book` | `sdk.Shape.Book` |

---

## Quick reference

```python
from agentos import molt, http, shape, get_cookies

# --- molt: clean + parse ---
molt(s)                          # clean string
molt(s, int)                     # parse integer
molt(s, float)                   # parse float
molt(s, 'date')                  # parse to ISO 8601
molt(timestamp, 'date')          # convert ms/s timestamp

# --- http: engine-routed requests ---
http.get(url)                                    # simple GET
http.post(url, json={...})                       # POST with JSON body
http.get(url, cookies=header)                    # with session cookies
http.get(url, **http.headers(accept="json"))     # JSON API headers
http.get(url, **http.headers(waf="cf"))          # CloudFront/Cloudflare WAF bypass
http.client(cookies=header)                      # session with cookie jar
http.headers(waf=, accept=, mode=, extra=)       # build header config
get_cookies(params)                              # extract cookies from runtime params

# --- shape: typed entities ---
shape.Book                       # TypedDict with book fields
shape.Person                     # TypedDict with person fields
shape.Account                    # TypedDict with account fields
```
