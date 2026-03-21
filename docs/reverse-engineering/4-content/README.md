# Reverse Engineering — Content Extraction from HTML

When there's no API, no GraphQL, no Apollo cache — just server-rendered HTML
behind a login wall. This doc covers the patterns for authenticated HTML scraping
with `httpx` + BeautifulSoup.

This is Layer 4 of the reverse-engineering docs:

- **Layer 1: Transport** — [1-transport](../1-transport/index.html) — getting a response at all
- **Layer 2: Discovery** — [2-discovery](../2-discovery/index.html) — finding structured data in bundles
- **Layer 3: Auth & Runtime** — [3-auth](../3-auth/index.html) — credentials, sessions, rotating config
- **Layer 4: Content** (this file) — extracting data from HTML when there is no API
- **Layer 5: Social Networks** — [5-social](../5-social/index.html) — modeling people, relationships, and social graphs
- **Layer 6: Desktop Apps** — [6-desktop-apps](../6-desktop-apps/index.html) — macOS, Electron, local state, unofficial APIs

---

## When You Need This Layer

Not every operation needs HTML scraping. The same site often has a mix:

| Data type | Approach | Example |
|---|---|---|
| Public catalog data | GraphQL / Apollo cache (Layer 2) | Goodreads book details, reviews, search |
| User-scoped data behind login | HTML scraping (this doc) | Goodreads friends, shelves, user's books |
| Write operations | API calls with session tokens | Rating a book, adding to shelf |

**Rule of thumb:** Check for structured APIs first (Layer 2). Only fall back to
HTML scraping when the data is exclusively server-rendered behind authentication.

---

## Skill Architecture: Two Modules

When a skill needs both public API access and authenticated scraping, split into
two Python modules:

```
skills/mysite/
  readme.md          # Skill descriptor — operations point to either module
  public_graph.py    # Public API / GraphQL / Apollo — no cookies needed
  web_scraper.py     # Authenticated HTML scraping — needs cookies
```

The readme declares separate connections for each:

```yaml
connections:
  graphql:
    description: "Public API — key auto-discovered"
  web:
    description: "User cookies for authenticated data"
    cookies:
      domain: ".mysite.com"
    optional: true
    label: MySite Session
```

Operations reference the appropriate connection:

```yaml
operations:
  search_books:        # public
    connection: graphql
    python:
      module: ./public_graph.py
      function: search_books
      args: { query: .params.query }

  list_friends:        # authenticated
    connection: web
    python:
      module: ./web_scraper.py
      function: run_list_friends
      params: true
```

---

## Cookie Flow: `connection: web` → Python

The entire cookie lifecycle is handled by agentOS. The Python script never
touches browser databases or knows which browser the cookies came from.

### How it works

1. Skill declares `connection: web` with `cookies.domain: ".mysite.com"`
2. Executor finds an installed cookie provider (`brave-browser`, `firefox`, etc.)
3. Provider extracts + decrypts cookies from the local browser database
4. Executor injects them into params as `params.auth.cookies` (a `Cookie:` header string)
5. Python reads them and passes to httpx

### Python side

```python
def _cookie(ctx: dict) -> str | None:
    """Extract cookie header from AgentOS-injected auth."""
    c = (ctx.get("auth") or {}).get("cookies") or ""
    return c if c else None

def _require_cookies(cookie_header, params, op_name):
    cookie_header = cookie_header or (params and _cookie(params))
    if not cookie_header:
        raise ValueError(f"{op_name} requires session cookies (connection: web)")
    return cookie_header
```

### `params: true` context structure

When a Python executor uses `params: true`, the function receives the full
wrapped context as a single `params` dict:

```json
{
  "params": { "user_id": "123", "page": 1 },
  "auth": { "cookies": "session_id=abc; token=xyz" }
}
```

Use a helper to read user params from either nesting level:

```python
def _p(d: dict, key: str, default=None):
    """Read from params sub-dict or top-level."""
    p = (d.get("params") or d) if isinstance(d, dict) else {}
    return p.get(key, default) if isinstance(p, dict) else default
```

---

## HTTP Client: Shared Across Pages

Create one `httpx.Client` per operation and reuse it across paginated requests.
This keeps the TCP/TLS connection alive and avoids per-request overhead.

```python
def _client(cookie_header: str | None) -> httpx.Client:
    headers = dict(STANDARD_HEADERS)
    if cookie_header:
        headers["Cookie"] = cookie_header
    return httpx.Client(http2=True, follow_redirects=True, timeout=30, headers=headers)

# Usage
with _client(cookie_header) as client:
    for page in range(1, max_pages + 1):
        status, html = _fetch(client, url.format(page=page))
        if not _has_next(html):
            break
```

---

## Pagination

### Default: fetch all pages

Make `page=0` the default, meaning "fetch everything." When the caller passes
`page=N`, return only that page. This gives callers control without requiring
them to implement their own pagination loop.

```python
def list_friends(user_id, page=0, cookie_header=None, *, params=None):
    if page > 0:
        # Single page
        return _parse_one_page(url.format(page=page), cookie_header)

    # Auto-paginate
    all_items = []
    seen = set()
    with _client(cookie_header) as client:
        for p in range(1, MAX_PAGES + 1):
            status, html = _fetch(client, url.format(page=p))
            items = _parse_page(html)
            for item in items:
                if item["id"] not in seen:
                    seen.add(item["id"])
                    all_items.append(item)
            if not items or not _has_next(html):
                break
    return all_items
```

### Detecting "next page"

Look for pagination controls rather than guessing based on result count:

```python
def _has_next(html_text: str) -> bool:
    return bool(
        re.search(r'class="next_page"', html_text) or
        re.search(r'rel="next"', html_text)
    )
```

### Safety limits

Always cap auto-pagination (`MAX_PAGES = 20`). A user with 5,000 books shouldn't
trigger 200 sequential requests in a single tool call.

### Deduplication

Sites often include the user's own profile in friend lists, or repeat items
across page boundaries. Always deduplicate by ID:

```python
seen: set[str] = set()
for item in page_items:
    if item["id"] not in seen:
        seen.add(item["id"])
        all_items.append(item)
```

---

## HTML Parsing Patterns

### Use data attributes over visible text

Data attributes are more stable than CSS classes or visible text:

```python
# Good: data-rating is the source of truth
stars = row.select_one(".stars[data-rating]")
rating = int(stars["data-rating"]) if stars else None

# Bad: fragile, depends on star rendering
rating_el = row.select_one(".staticStars")
```

### Structured table pages (Goodreads `/review/list/`)

Many sites render user data in HTML tables with class-coded columns. Each `<td>`
has a field class you can target directly:

```python
rows = soup.select("tr.bookalike")
for row in rows:
    book_id = row.get("data-resource-id")
    title = row.select_one("td.field.title a").get("title")
    author = row.select_one("td.field.author a").get_text(strip=True)
    rating = row.select_one(".stars[data-rating]")["data-rating"]
    date_added = row.select_one("td.field.date_added span[title]")["title"]
```

### Extraction helpers

Write small focused helpers for each field type rather than inline parsing:

```python
def _extract_date(row, field_class):
    td = row.select_one(f"td.field.{field_class}")
    if not td:
        return None
    span = td.select_one("span[title]")
    if span:
        return span.get("title") or span.get_text(strip=True)
    return None

def _extract_rating(row):
    stars = row.select_one(".stars[data-rating]")
    if stars:
        val = int(stars.get("data-rating", "0"))
        return val if val > 0 else None
    return None
```

### Login detection

Check early and fail fast when cookies are invalid:

```python
def _require_login(html_text):
    snippet = html_text[:2000]
    if "Sign in" in snippet or "Sign Up" in snippet:
        title = re.search(r"<title>(.*?)</title>", html_text, re.S)
        if title and ("Sign Up" in title.group(1) or "Sign in" in title.group(1)):
            raise RuntimeError("Page requires login — cookies invalid or expired")
```

---

## Adapter Null Safety

When a skill's adapter maps nested collections (like `shelves` on an `account`),
not every operation returns those nested fields. Use jaq `// []` fallback to
prevent null iteration errors:

```yaml
adapters:
  account:
    id: .user_id
    name: .name
    shelves:
      shelf[]:
        _source: '.shelves // []'    # won't blow up when shelves is absent
        id: .shelf_id
        name: .name
```

---

## Data Validation Checklist

After building a scraper, cross-reference against the live site:

| Check | How |
|---|---|
| **Total count** | Compare your result count to what the site header says ("Showing 1-30 of 69") |
| **Unique IDs** | Deduplicate and compare — off-by-one usually means a deleted/deactivated account |
| **Rating counts** | Count items with non-null ratings vs. the site's "X ratings" display |
| **Review counts** | Count items with actual review text vs. the site's "X reviews" display |
| **Field completeness** | Spot-check dates, ratings, authors against individual entries on the site |
| **Shelf math** | Sum shelf counts and compare to "All (N)" — they may diverge (Goodreads shows 273 but serves 301) |

---

## Testing Methodology

### 1. Save cookies locally for development

Extract cookies once and save to a JSON file for local testing:

```python
# From agentOS:
# run({ skill: "brave-browser", tool: "cookie_get", params: { domain: ".mysite.com" } })

# Or manually build the file:
# scripts/test_cookies.json
[
  {"name": "session_id", "value": "abc123", "domain": ".mysite.com"},
  ...
]
```

### 2. Test parsers against real pages

Hit the live site with httpx and verify parsing before wiring to agentOS:

```python
with open("scripts/test_cookies.json") as f:
    cookies = json.load(f)
cookie_header = "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)

friends = list_friends("12345", cookie_header=cookie_header)
print(f"Got {len(friends)} friends")
```

### 3. Test through agentOS MCP

Once local parsing works, test the full pipeline:

```bash
npm run mcp:call -- --skill mysite --tool list_friends \
  --params '{"user_id":"12345"}' --verbose
```

### 4. Mark cookie-dependent tests as write mode

Operations that require live cookies should use `test.mode: write` so they're
skipped in automated smoke tests but can be run manually with `--write`:

```yaml
test:
  mode: write
  fixtures:
    user_id: "12345"
```

---

## Real-World Examples

| Skill | What's scraped | Reference |
|---|---|---|
| `skills/goodreads/` | People (friends, following, followers), books, reviews, groups, quotes, rich profiles — all from HTML | `web_scraper.py` |
| Future: `skills/myspace/` | Friends, followers, profile data from legacy HTML | — |
| Future: `skills/twitter/` | Following, followers, tweets, likes | — |

For social-network-specific modeling patterns (person vs account, relationship
types, cross-platform identity), see [5-social](../5-social/index.html).
