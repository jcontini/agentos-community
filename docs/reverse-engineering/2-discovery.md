# Reverse Engineering — Discovery & Data Extraction

Once you can talk to the server (see [1-transport.md](1-transport.md)),
how do you find and extract structured data?

This is Layer 2 of three reverse-engineering docs:

- **Layer 1: Transport** — [1-transport.md](1-transport.md)
- **Layer 2: Discovery** (this file) — finding structured data in pages and bundles
- **Layer 3: Auth & Runtime** — [3-auth.md](3-auth.md)

**Tool:** The Playwright skill (`skills/playwright/readme.md`) is the primary browser-based discovery tool. Use it to probe pages, inspect DOM/hydration state, capture network traffic, and extract cookies. The patterns in this doc tell you what to do with what Playwright finds.

---

## Next.js + Apollo Cache Extraction

Many modern sites (Goodreads, Airbnb, etc.) use Next.js with Apollo Client. These
pages ship a full serialized Apollo cache in the HTML — structured entity data that
you can parse without scraping visible HTML.

### Where to find it

```html
<script id="__NEXT_DATA__" type="application/json">{ ... }</script>
```

Inside that JSON:

```
__NEXT_DATA__
  .props.pageProps
  .props.pageProps.apolloState        <-- the gold
  .props.pageProps.apolloState.ROOT_QUERY
```

### How Apollo normalized cache works

Apollo stores GraphQL results as a flat dictionary keyed by entity type and ID.
Related entities are stored as `{"__ref": "Book:kca://book/..."}` pointers.

```python
import json, re

def extract_next_data(html: str) -> dict:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.S,
    )
    if not match:
        raise RuntimeError("No __NEXT_DATA__ found")
    return json.loads(match.group(1))

def deref(apollo: dict, value):
    """Resolve Apollo __ref pointers to their actual objects."""
    if isinstance(value, dict) and "__ref" in value:
        return apollo.get(value["__ref"])
    return value
```

### Extraction pattern

```python
next_data = extract_next_data(html)
apollo = next_data["props"]["pageProps"]["apolloState"]
root_query = apollo["ROOT_QUERY"]

# Find the entity by its query key
book_ref = root_query['getBookByLegacyId({"legacyId":"4934"})']
book = apollo[book_ref["__ref"]]

# Dereference related entities
work = deref(apollo, book.get("work"))
primary_author = deref(apollo, book.get("primaryContributorEdge", {}).get("node"))
```

### What you typically find in the Apollo cache

| Entity type | Common fields |
|---|---|
| Books | title, description, imageUrl, webUrl, legacyId, details (isbn, pages, publisher) |
| Contributors | name, legacyId, webUrl, profileImageUrl |
| Works | stats (averageRating, ratingsCount), details (originalTitle, publicationTime) |
| Social signals | shelf counts (CURRENTLY_READING, TO_READ) |
| Genres | name, webUrl |
| Series | title, webUrl |

The Apollo cache often contains more data than the visible page renders. Always
dump and inspect `apolloState` before assuming you need to make additional API calls.

### Real example: Goodreads

See `skills/goodreads/public_graph.py` functions `load_book_page()` and
`map_book_payload()` for a complete implementation that extracts 25+ fields from
the Apollo cache without any GraphQL calls.

---

## JS Bundle Config Discovery

SPAs embed configuration — API keys, endpoints, tenant IDs — in their minified
JavaScript bundles. This is findable without login.

### General pattern

```python
import re

def discover_config_from_bundle(html: str, base_url: str) -> dict:
    # Step 1: find the main JS bundle URL in the HTML
    bundle_match = re.search(r'(/assets/app-[A-Za-z0-9]+\.js)', html)
    # For Next.js apps:
    bundle_match = re.search(r'(/_next/static/chunks/pages/_app-[a-f0-9]+\.js)', html)

    # Step 2: fetch the bundle
    bundle_js = fetch(f"{base_url}{bundle_match.group()}")

    # Step 3: regex-extract config values
    configs = {}
    for m in re.finditer(r'"apiKey":"([^"]+)"', bundle_js):
        configs[m.group(1)] = True
    return configs
```

### Common patterns to search for

| What | Regex pattern |
|---|---|
| API keys | `apiKey`, `api_key`, `X-Api-Key`, `widgetsApiKey` |
| GraphQL endpoints | `appsync-api.*amazonaws\.com`, `graphql` |
| Tenant / namespace | `host.split(".")[0]` or hardcoded subdomain strings |
| Cognito credentials | `userPoolId`, `userPoolClientId` near `aws:` |
| Auth endpoints | `AuthFlow`, `InitiateAuth`, `cognito-idp` |

### Multi-environment configs

Many sites ship all environment configs in the same bundle. Goodreads ships four
AppSync configurations with labeled environments:

```json
{"graphql":{"apiKey":"da2-...","endpoint":"https://...appsync-api...amazonaws.com/graphql","region":"us-east-1"},"showAds":false,"shortName":"Dev"}
{"graphql":{"apiKey":"da2-...","endpoint":"https://...appsync-api...amazonaws.com/graphql","region":"us-east-1"},"showAds":false,"shortName":"Beta"}
{"graphql":{"apiKey":"da2-...","endpoint":"https://...appsync-api...amazonaws.com/graphql","region":"us-east-1"},"showAds":true,"shortName":"Preprod"}
{"graphql":{"apiKey":"da2-...","endpoint":"https://...appsync-api...amazonaws.com/graphql","region":"us-east-1"},"showAds":true,"shortName":"Prod"}
```

Pick the right one by looking for identifiers like `shortName`, `showAds: true`,
`publishWebVitalMetrics: true`, or simply taking the last entry (Prod is typically
last in webpack build output).

### The "Authorization is the namespace" pattern

Some APIs use the `Authorization` header not for a JWT but for a tenant namespace
extracted from the subdomain at runtime:

```js
Jl = () => host.split(".")[0]   // -> "boulderingproject"
headers: { Authorization: Jl(), "X-Api-Key": widgetsApiKey }
```

If you see `Authorization` values that seem too short to be JWTs, look for the
function that generates them near the axios/fetch client factory in the bundle.

### Real examples

- Goodreads: `skills/goodreads/public_graph.py` `discover_from_bundle()` — extracts Prod AppSync config from `_app` chunk
- Austin Boulder Project: `skills/austin-boulder-project/abp.py` — API key and namespace from Tilefive bundle

---

## GraphQL Schema Discovery via JS Bundles

Production GraphQL endpoints almost never allow introspection queries. But the
frontend JS bundles contain every query and mutation the app uses.

### Technique: scan all JS chunks for operation names

```python
import re

def discover_graphql_operations(html: str, base_url: str) -> set[str]:
    """Find all GraphQL operation names from the frontend JS bundles."""
    chunks = re.findall(r'(/_next/static/chunks/[a-zA-Z0-9/_%-]+\.js)', html)
    operations = set()
    for chunk in chunks:
        js = fetch(f"{base_url}{chunk}")
        # Find query/mutation declarations
        for m in re.finditer(r'(?:query|mutation)\s+([A-Za-z_]\w*)\s*[\(\{]', js):
            operations.add(m.group(1))
    return operations
```

### What this finds

On Goodreads, scanning 18 JS chunks revealed 38 operations:

**Queries (public reads):** `getReviews`, `getSimilarBooks`, `getSearchSuggestions`,
`getWorksByContributor`, `getWorksForSeries`, `getComments`, `getBookListsOfBook`,
`getSocialSignals`, `getWorkCommunityRatings`, `getWorkCommunitySignals`, ...

**Queries (auth required):** `getUser`, `getViewer`, `getEditions`,
`getSocialReviews`, `getWorkSocialReviews`, `getWorkSocialShelvings`, ...

**Mutations:** `RateBook`, `ShelveBook`, `UnshelveBook`, `TagBook`, `Like`,
`Unlike`, `CreateComment`, `DeleteComment`

### Extracting full query strings

Once you know the operation name, extract the full query with its variable shape:

```python
def extract_query(js: str, operation_name: str) -> str | None:
    idx = js.find(f"query {operation_name}")
    if idx == -1:
        return None
    snippet = js[idx:idx + 3000]
    depth = 0
    for i, c in enumerate(snippet):
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return snippet[:i + 1].replace("\\n", "\n")
    return None
```

This gives you copy-pasteable GraphQL documents you can replay directly via HTTP POST.

### Real example: Goodreads

See `skills/goodreads/public_graph.py` for the full set of proven GraphQL queries
including `getReviews`, `getSimilarBooks`, `getSearchSuggestions`,
`getWorksForSeries`, and `getWorksByContributor`.

---

## Public vs Auth Boundary Mapping

After discovering operations, you need to determine which ones work anonymously
(with just the public API key) and which require user session auth.

### Technique: probe each operation and classify the error

Send each discovered operation to the public endpoint and classify the response:

| Response | Meaning |
|---|---|
| `200` with `data` | Public, works anonymously |
| `200` with `errors: ["Not Authorized to access X on type Y"]` | Partially public — the operation works but specific fields are viewer-scoped. Remove the blocked field and retry. |
| `200` with `errors: ["MappingTemplate" / VTL error]` | Requires auth — the AppSync resolver needs session context to even start |
| `403` or `401` | Requires auth at the transport level |

### AppSync VTL errors as a signal

AWS AppSync uses Velocity Template Language (VTL) resolvers. When a public request
hits an auth-gated resolver, you get a distinctive error:

```json
{
  "errorType": "MappingTemplate",
  "message": "Error invoking method 'get(java.lang.Integer)' in [Ljava.lang.String; at velocity[line 20, column 55]"
}
```

This means: "the resolver tried to read user context from the auth token and failed."
It reliably indicates the operation needs authentication.

### Field-level authorization

GraphQL auth on AppSync is often field-level, not operation-level. A `getReviews`
query might work but including `viewerHasLiked` returns:

```json
{ "message": "Not Authorized to access viewerHasLiked on type Review" }
```

The fix: remove the viewer-scoped field from your query. The rest works fine publicly.

### Goodreads boundary scorecard

| Operation | Public? | Notes |
|---|---|---|
| `getSearchSuggestions` | Yes | Book search by title/author |
| `getReviews` | Yes | Except `viewerHasLiked` and `viewerRelationshipStatus` |
| `getSimilarBooks` | Yes | |
| `getWorksForSeries` | Yes | Series book listings |
| `getWorksByContributor` | Yes | Needs internal contributor ID (not legacy author ID) |
| `getUser` | No | VTL error — needs session |
| `getEditions` | No | VTL error — needs session |
| `getViewer` | No | Viewer-only by definition |
| `getWorkSocialShelvings` | Partial | May need session for full data |

---

## Heterogeneous Page Stacks

Large sites migrating to modern frontends have mixed page types. You need to
identify which pages use which stack and adjust your extraction strategy.

### How to identify the stack

| Signal | Stack |
|---|---|
| `<script id="__NEXT_DATA__">` in HTML | Next.js (server-rendered, may have Apollo cache) |
| GraphQL/AppSync XHR traffic after page load | Modern frontend with GraphQL backend |
| No `__NEXT_DATA__`, classic `<div>` structure, `<meta>` tags | Legacy server-rendered HTML |
| `window.__INITIAL_STATE__` or similar | React SPA with custom state hydration |

### Goodreads example

| Page type | Stack | Extraction strategy |
|---|---|---|
| Book pages (`/book/show/`) | Next.js + Apollo + AppSync | `__NEXT_DATA__` for main data, GraphQL for reviews/similar |
| Author pages (`/author/show/`) | Legacy HTML | Regex scraping |
| Profile pages (`/user/show/`) | Legacy HTML | Regex scraping |
| Search pages (`/search`) | Legacy HTML | Regex scraping |

Strategy: use structured extraction where available, fall back to HTML only where
the site hasn't migrated yet. As the site migrates pages, move your extractors to
match.

---

## Legacy HTML Scraping

When a page has no structured data surface, regex scraping is the fallback.

### Principles

- Prefer specific anchors (IDs, class names, `itemprop` attributes) over positional matching
- Use `re.S` (dotall) for multi-line HTML patterns
- Extract sections first, then parse within the section to reduce false matches
- Always strip and unescape HTML entities

### Section extraction pattern

```python
def section_between(html: str, start_marker: str, end_marker: str) -> str:
    start = html.find(start_marker)
    if start == -1:
        return ""
    end = html.find(end_marker, start)
    return html[start:end] if end != -1 else html[start:]
```

### When to stop scraping

If you find yourself writing regex patterns longer than 3 lines, consider:

1. Is there a `__NEXT_DATA__` payload you missed?
2. Does the page make XHR calls you could replay directly?
3. Can you use a headless browser to get the rendered DOM instead?

HTML scraping should be the strategy of last resort, not the first attempt.

---

## Real-World Examples in This Repo

| Skill | Discovery technique | Reference |
|---|---|---|
| `skills/goodreads/` | Next.js Apollo cache + AppSync GraphQL + JS bundle scanning | `public_graph.py` |
| `skills/austin-boulder-project/` | JS bundle config extraction (API key + namespace) | `abp.py` |
| `skills/claude/` | Session cookie capture via Playwright | `claude-login.py` |
