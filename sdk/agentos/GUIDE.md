
# agentOS Skill Development Guide

> This is everything you need to build an agentOS skill.
> Read it once, build a skill. No other docs required.

## What is a skill?

A skill connects agentOS to an external service. It's **two files** in a directory:

```
skills/my-skill/
  readme.md      # identity + config (YAML frontmatter)
  my_skill.py    # operations (decorated Python functions)
```

The engine reads both at boot:
- `readme.md` frontmatter → identity, connections, test config
- `*.py` files → operations (via AST parsing, never executed at boot)

## Skill anatomy

### readme.md — identity and config

```markdown
---
id: my-skill
name: My Skill
description: What this skill does in one line
color: "#4A90D9"
website: https://example.com

connections:
  api:
    base_url: https://api.example.com
    auth:
      type: api_key
      header:
        x-api-key: .auth.key
    label: API Key
    help_url: https://example.com/api-keys

test:
  list_items: { params: { query: "test" } }
  get_item: { params: { id: "123" } }
---

# My Skill

Description of what this skill connects to and what data it provides.
```

**Required frontmatter fields:** `id`, `name`

**Connection auth types:**
- `api_key` — API key in a header or query param
- `cookies` — browser session cookies (domain required)
- `oauth` — OAuth2 refresh token flow
- `none` — no auth needed (omit the connections block entirely)

### Python module — operations

```python
"""My Skill — connects to Example API for items and searches."""

from agentos import http, returns

@returns("product[]")
def list_items(query: str = None, limit: int = 10, **params) -> list[dict]:
    """List items matching a query.

    Args:
        query: Search query to filter items
        limit: Max results to return (default 10)
    """
    resp = http.get("https://api.example.com/items",
                    params={"q": query, "limit": limit},
                    headers={"x-api-key": params["auth"]["key"]})
    return [{"id": str(item["id"]),
             "name": item["title"],
             "url": f"https://example.com/items/{item['id']}",
             "price": item.get("price"),
             "currency": item.get("currency", "USD")}
            for item in resp["json"]["items"]]
```

**Rules:**
- Every public function is an operation (underscore-prefixed = private)
- Every operation MUST have `@returns("shape")` or `@returns("shape[]")`
- Every operation MUST accept `**params` — the engine injects auth, context
- First line of docstring = operation description (shown in MCP tool schema)
- `Args:` section (Google style) = parameter descriptions
- Type hints on params = schema types (`str`, `int`, `bool`, `float`)
- Default values = optional params; no default = required

## SDK modules

All I/O goes through SDK modules. **Never** import `urllib`, `requests`,
`subprocess`, `sqlite3`, or `os.popen` — the engine sandbox blocks them.

### http — HTTP requests

```python
from agentos import http

# Simple GET
resp = http.get("https://api.example.com/data")
data = resp["json"]          # parsed JSON (dict/list)
html = resp["body"]          # raw response body (string)
code = resp["status"]        # HTTP status code (int)
ok   = resp["ok"]            # True if 2xx

# POST with JSON body
resp = http.post("https://api.example.com/items",
                 json={"name": "test"},
                 headers={"Authorization": "Bearer token"})

# POST with form data
resp = http.post("https://api.example.com/login",
                 data={"username": "u", "password": "p"})

# All methods: get, post, put, patch, delete, head
```

### http.headers() — browser-like headers for cookie-auth skills

This is the most important function for cookie-auth skills. WAFs (Cloudflare,
CloudFront, Vercel) block requests that don't look like a real browser.

```python
from agentos import http

# Spread into any request with **
resp = http.get(url, **http.headers(waf="cf", mode="navigate", accept="html"))
```

**Knobs (compose independently):**

| Knob | Values | Default | What it does |
|------|--------|---------|-------------|
| `waf` | `"cf"`, `"vercel"`, `None` | `None` | WAF vendor — adds Sec-CH-UA client hints. `"cf"` covers both Cloudflare and CloudFront |
| `ua` | `"chrome-desktop"`, `"chrome-mobile"`, `"safari-desktop"`, or raw string | `"chrome-desktop"` | User-Agent header |
| `mode` | `"fetch"`, `"navigate"` | `"fetch"` | Request type — `"navigate"` adds Sec-Fetch-Dest: document + full browser hints |
| `accept` | `"json"`, `"html"`, `"any"` | `"any"` | Accept header — `"html"` sends the full browser Accept string |
| `extra` | dict | `None` | Additional headers merged last (highest priority) |

**Returns** a dict with `"headers"` (and optionally `"http2": bool`). The `**`
spread passes both to `http.get/post`.

**When to use what:**

| Scenario | Headers call |
|----------|-------------|
| Public JSON API (no auth) | No headers needed — just `http.get(url)` |
| API with key in header | `headers={"x-api-key": key}` — no `http.headers()` needed |
| Cookie-auth, Cloudflare/CloudFront | `http.headers(waf="cf", mode="navigate", accept="html")` |
| Cookie-auth, Vercel | `http.headers(waf="vercel", mode="navigate", accept="html")` |
| Cookie-auth, no WAF | `http.headers(mode="navigate", accept="html")` |
| XHR/fetch to same-origin API | `http.headers(waf="cf", mode="fetch", accept="json")` |
| GraphQL endpoint | `http.headers(accept="json", extra={"Content-Type": "application/json"})` |

**Anti-bot patterns:**

- `mode="navigate"` adds `Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate`,
  `Cache-Control: max-age=0`, `Upgrade-Insecure-Requests: 1`, device memory hints,
  and DPR/viewport hints. This mimics a user clicking a link.
- `mode="fetch"` adds `Sec-Fetch-Dest: empty`, `Sec-Fetch-Mode: cors` — mimics
  JavaScript `fetch()` from within a page.
- `waf="cf"` adds `Sec-CH-UA` client hints that match Chrome's real values.
  Without these, Cloudflare/CloudFront returns 403.
- `waf="vercel"` disables HTTP/2 — Vercel's checkpoint blocks non-browser h2
  fingerprints with 429.

**What the engine auto-injects vs what Python must set:**

The engine provides:
- TLS fingerprint emulation (Chrome 145 via wreq) — automatic, not configurable
- Cookie jar management (Set-Cookie tracking, writeback)
- HTTP/2 toggle (from `http2` key in headers() return)

Python (your skill) provides via `http.headers()`:
- User-Agent
- Sec-CH-UA and other client hints
- Sec-Fetch-* metadata
- Accept / Accept-Language / Accept-Encoding
- Any custom headers (Authorization, Referer, Origin, etc.)

The engine is pure transport — it does NOT add browser headers automatically.
If you don't call `http.headers()`, requests go out with no User-Agent, no
Accept, no hints. For public APIs this is fine. For cookie-auth sites, you
**must** use `http.headers()`.

### http.client() — session with cookie jar

For multi-request flows where cookies matter (login → navigate → scrape):

```python
from agentos import http, require_cookies

cookie_header = require_cookies(params, "list_orders")

with http.client(cookies=cookie_header) as c:
    # First request — sets session cookies
    c.get("https://www.example.com/",
          **http.headers(waf="cf", mode="navigate", accept="html"))
    # Second request — cookies from first request are sent automatically
    resp = c.get("https://www.example.com/account/orders",
                 **http.headers(waf="cf", mode="navigate", accept="html"))
    orders = resp["body"]
```

The engine tracks `Set-Cookie` responses and diffs the jar on session close
for automatic writeback to the credential store.

### http.cookies() — resolve cookies by domain

```python
from agentos import http

cookie_header = http.cookies(".uber.com")
# Returns "name=value; name=value; ..." from best available provider
```

Uses the auth system's provider discovery: tries all installed cookie providers
(brave-browser, firefox), picks the freshest session, validates it.

### Cookie helpers

```python
from agentos import get_cookies, require_cookies, parse_cookie

# Get cookies from params (returns None if not present)
cookies = get_cookies(params)

# Get cookies or raise with helpful message
cookies = require_cookies(params, "operation_name")

# Extract a single cookie value
session_id = parse_cookie(cookie_header, "session_id")
```

### sql — database queries

```python
from agentos import sql

# Read query (returns list of row dicts)
rows = sql.query("SELECT id, name FROM users WHERE active = :active",
                 db="~/Library/Application Support/App/data.sqlite",
                 params={"active": 1})

# Write query
sql.execute("INSERT INTO items (name) VALUES (:name)",
            db="~/data.db", params={"name": "test"})

# Cross-database JOIN
rows = sql.query("SELECT m.id FROM main.items m JOIN other.tags t ON ...",
                 db="~/main.db",
                 attach={"other": "~/tags.db"})
```

Use this instead of `import sqlite3`. The engine handles path resolution,
logging, and permissions.

### shell — binary execution

```python
from agentos import shell

result = shell.run("git", ["log", "--oneline", "-5"], cwd="/path/to/repo")
print(result["stdout"])      # captured stdout
print(result["stderr"])      # captured stderr
print(result["exit_code"])   # 0 = success
```

Shell interpreters (bash, sh, zsh) are always blocked. Run binaries directly.
Use this instead of `import subprocess`.

### crypto — browser cookie decryption

```python
from agentos import crypto

key = crypto.pbkdf2(password="peanuts", salt="saltysalt",
                    iterations=1003, length=16)
plaintext = crypto.aes_decrypt(key=key, data=encrypted_hex)
```

Used by browser cookie providers. You probably won't need this directly.

### oauth — token exchange

```python
from agentos import oauth

token = oauth.exchange(
    token_url="https://oauth2.googleapis.com/token",
    refresh_token=params["auth"]["refresh_token"],
    client_id=params["auth"]["client_id"],
)
access_token = token["access_token"]
```

### text — cleaning scraped data

```python
from agentos import molt

molt(s)                          # clean string (strip HTML, normalize whitespace, kill sentinels)
molt("1,234 reviews", int)       # 1234
molt("4.5 out of 5", float)     # 4.5
molt("August 2010", "date")     # "2010-08"
molt(1616025600000, "date")     # "2021-03-18T..."
molt(None)                       # None

# Fine-grained imports if you need specific behavior:
from agentos import clean_text, clean_html, strip_tags
from agentos import parse_int, parse_float, parse_date
from agentos import iso_from_ms, iso_from_seconds
```

`molt()` is the universal cleaner — use it for any scraped value. It handles
HTML entities, whitespace normalization, and sentinel detection ("N/A",
"not available", etc. → `None`).

## Decorators

```python
from agentos import returns, provides, connection, timeout
```

### @returns(shape) — required on every operation

```python
@returns("event[]")          # returns list of events
def list_events(...): ...

@returns("event")            # returns single event
def get_event(...): ...

@returns({"ok": "boolean"})  # inline schema (no shape reference)
def delete_item(...): ...
```

The engine reads this via AST — it's a no-op at runtime.

### @provides(tool) — register as a standard capability

```python
from agentos import provides, web_search, web_read

@provides(web_search)
def search(query: str, **params) -> list[dict]: ...

@provides(web_read, urls=["example.com/*"])
def read_page(url: str, **params) -> dict: ...
```

Standard tool constants (import from `agentos`):
- `web_search`, `web_read` — discovery & retrieval
- `email_lookup` — people
- `flight_search`, `geocoding`, `map_tiles` — travel
- `file_list`, `file_read`, `file_info` — files
- `cookie_auth`, `oauth_auth` — auth provision

### @connection(name) — bind to auth connection

```python
@connection("web")           # uses the "web" connection from frontmatter
def list_orders(...): ...

@connection("api")           # uses the "api" connection
def search(...): ...
```

Tells the engine which connection's credentials to inject into `params["auth"]`.

### @timeout(seconds) — override default 30s timeout

```python
@timeout(60)                 # allow up to 60 seconds
def slow_operation(...): ...
```

## Shape conventions

Shapes define the structure of entities. Shape field names are **camelCase**.

**Standard fields** (available on all shapes):
- `id` (string) — unique identifier
- `name` (string) — display name
- `url` (string) — canonical URL
- `image` (string) — image URL
- `published` (datetime) — when created/published
- `content` (string) — main text content

**Example — returning an event shape:**

```python
@returns("event[]")
def list_events(**params) -> list[dict]:
    return [{
        "id": "evt-123",
        "name": "Python Meetup",
        "url": "https://meetup.com/events/123",
        "startDate": "2026-04-10T18:00:00Z",    # camelCase!
        "endDate": "2026-04-10T20:00:00Z",
        "timezone": "America/Chicago",
        "eventType": "meetup",
        "status": "confirmed",
        "allDay": False,
    }]
```

**Common shapes:** event, product, person, account, book, email, post, result,
webpage, order, review, article, place, domain, channel, conversation.

Use `agent-sdk shapes` to list all shapes. Use `agent-sdk shapes event` to see
a shape's fields and relations.

## Annotated examples

### Example 1: Public API skill (no auth)

```python
"""Curl — simple URL fetching via HTTP GET."""

from lxml import html
from agentos import http, provides, returns, timeout, web_read

@returns("webpage")
@provides(web_read)
@timeout(35)
def read_webpage(*, url: str, **params) -> dict:
    """Fetch a URL and return its content, title, and content type."""
    resp = http.get(url, timeout=30.0)
    content = resp["body"]
    content_type = resp["headers"].get("content-type", "text/plain").split(";")[0].strip()

    title = ""
    if content_type.startswith("text/html") and content:
        doc = html.fromstring(content[:4000])
        title_el = doc.cssselect("title")
        if title_el:
            title = title_el[0].text_content().strip()

    return {
        "id": url,
        "name": title or url,
        "url": url,
        "content": content,
        "contentType": content_type,
    }
```

**Pattern:** No auth, no `http.headers()`, no `@connection`. Just `http.get()`.

### Example 2: Cookie-auth skill (Goodreads)

```python
"""Goodreads — profile, books, and reviews via session cookies."""

from lxml import html as lxml_html
from agentos import http, molt, returns, connection, timeout
from agentos import get_cookies, require_cookies

@returns("person")
@connection("web")
@timeout(30)
def get_person(user_id: str, **params) -> dict:
    """Get a Goodreads user profile."""
    cookies = require_cookies(params, "get_person")

    with http.client(cookies=cookies) as c:
        resp = c.get(f"https://www.goodreads.com/user/show/{user_id}",
                     **http.headers(waf="cf", mode="navigate", accept="html"))

    doc = lxml_html.fromstring(resp["body"])
    name_el = doc.cssselect("h1.userProfileName")
    return {
        "id": user_id,
        "name": molt(name_el[0].text_content()) if name_el else user_id,
        "url": f"https://www.goodreads.com/user/show/{user_id}",
        "platform": "goodreads.com",
    }
```

**Pattern:** `@connection("web")` → engine injects cookies into `params["auth"]`.
`require_cookies()` extracts them. `http.headers(waf="cf")` for CloudFront WAF.
`lxml` + `cssselect` for HTML parsing. `molt()` to clean scraped text.

### Example 3: API-key skill (Exa)

```python
"""Exa — semantic web search and content extraction."""

from agentos import http, returns, provides, connection, timeout, web_search

@returns("result[]")
@provides(web_search)
@connection("api")
@timeout(30)
def search(query: str, limit: int = 10, **params) -> list[dict]:
    """Search the web using Exa's neural search."""
    resp = http.post("https://api.exa.ai/search",
                     json={"query": query, "numResults": limit,
                           "type": "auto", "useAutoprompt": True},
                     headers={"x-api-key": params["auth"]["key"]},
                     **http.headers(accept="json"))
    return [{"id": r["url"],
             "name": r.get("title", r["url"]),
             "url": r["url"],
             "content": r.get("text", ""),
             "published": r.get("publishedDate")}
            for r in resp["json"].get("results", [])]
```

**Pattern:** `@connection("api")` → engine injects API key into
`params["auth"]["key"]`. Header set directly on request.

## Common mistakes

**Blocked imports** — the sandbox blocks direct network/system access:
```python
# WRONG
import urllib.request        # use http.get()
import requests              # use http.get()
import subprocess            # use shell.run()
import sqlite3               # use sql.query()
import os; os.popen(...)     # use shell.run()

# RIGHT
from agentos import http, sql, shell
```

**snake_case dict keys** — shape fields are camelCase:
```python
# WRONG
return {"start_date": "2026-04-10", "event_type": "meetup"}

# RIGHT
return {"startDate": "2026-04-10", "eventType": "meetup"}
```

**Missing `**params`** — every operation must accept it:
```python
# WRONG
def list_items(query: str) -> list[dict]: ...

# RIGHT
def list_items(query: str, **params) -> list[dict]: ...
```

**Missing `@returns`** — every public function needs it:
```python
# WRONG
def list_items(**params): ...

# RIGHT
@returns("product[]")
def list_items(**params) -> list[dict]: ...
```

**No http.headers() on cookie-auth requests** — will get blocked by WAFs:
```python
# WRONG — naked request to a cookie-auth site
resp = http.get("https://www.goodreads.com/user/show/123",
                headers={"Cookie": cookies})

# RIGHT — full browser headers
resp = http.get("https://www.goodreads.com/user/show/123",
                cookies=cookies,
                **http.headers(waf="cf", mode="navigate", accept="html"))
```

**Using BeautifulSoup** — use lxml with cssselect:
```python
# WRONG
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, "html.parser")

# RIGHT
from lxml import html
doc = html.fromstring(body)
elements = doc.cssselect("div.item")
```

**Hardcoded User-Agent** — use http.headers():
```python
# WRONG
headers = {"User-Agent": "Mozilla/5.0 ..."}

# RIGHT
http.headers(ua="chrome-desktop")  # or just http.headers() — chrome-desktop is default
```

## Special return keys

Operations can return special keys alongside or instead of shape data:

```python
# Store credentials (cookies, API keys) in the credential store
return {"__secrets__": [http.skill_secret(
    domain=".exa.ai",
    identifier=email,
    item_type="session",
    value={"session_token": token},
)]}

# Cache runtime state (endpoints, discovered keys) on the skill's graph node
return {"__cache__": {"graphql_endpoint": url, "api_key": key}}

# Return structured result with metadata
return http.skill_result(status="code_sent", email=email)

# Return structured error
return http.skill_error("API key expired", status=401)
```

## Quick reference

| Import | What |
|--------|------|
| `from agentos import http` | HTTP client (get, post, put, patch, delete, head, client, headers, cookies) |
| `from agentos import sql` | Database queries (query, execute) |
| `from agentos import shell` | Binary execution (run) |
| `from agentos import crypto` | Crypto operations (pbkdf2, aes_decrypt) |
| `from agentos import oauth` | Token exchange (exchange) |
| `from agentos import molt` | Universal text cleaner |
| `from agentos import returns, provides, connection, timeout` | Decorators |
| `from agentos import web_search, web_read, ...` | Tool constants |
| `from agentos import get_cookies, require_cookies, parse_cookie` | Cookie helpers |
| `from agentos import skill_error, skill_result, skill_secret` | Result helpers |
| `from agentos import parse_int, parse_float, parse_date` | Type parsers |
| `from agentos import iso_from_ms, iso_from_seconds` | Timestamp converters |
| `from agentos import clean_text, clean_html, strip_tags` | Text cleaners |

## CLI commands

```bash
agent-sdk guide                    # print this guide
agent-sdk new-skill <name>         # scaffold a new skill
agent-sdk validate [dir]           # check skill for errors
agent-sdk shapes                   # list all shapes
agent-sdk shapes <name>            # show one shape's fields
```
""".strip()


def print_guide():
    """Print the skill development guide to stdout.
