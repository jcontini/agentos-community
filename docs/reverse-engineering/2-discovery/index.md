# Reverse Engineering — Discovery & Data Extraction

Once you can talk to the server (see [1-transport](../1-transport/index.md)),
how do you find and extract structured data?

This is Layer 2 of the reverse-engineering docs:

- **Layer 1: Transport** — [1-transport](../1-transport/index.md)
- **Layer 2: Discovery** (this file) — finding structured data in pages and bundles
- **Layer 3: Auth & Runtime** — [3-auth](../3-auth/index.md)
- **Layer 4: Content** — [4-content](../4-content/index.md) — HTML scraping when there is no API
- **Layer 5: Social Networks** — [5-social](../5-social/index.md) — modeling people, relationships, and social graphs
- **Layer 6: Desktop Apps** — [6-desktop-apps](../6-desktop-apps/index.md) — macOS, Electron, local state, unofficial APIs

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

## JS Bundle Scanning

SPAs embed everything in their JavaScript bundles — config values, API keys,
custom endpoints, and auth flow logic. Scanning bundles is one of the highest-
value reverse engineering techniques. It works without login, reveals hidden
endpoints that network capture misses, and exposes the exact contracts the
frontend uses.

### Two levels of bundle scanning

**Level 1: Config extraction** — find API keys, endpoints, tenant IDs.
Standard search for known patterns.

**Level 2: Endpoint and flow discovery** — find custom API endpoints that
aren't in the standard framework (e.g. `/api/verify-otp`), understand what
parameters they accept, and how the frontend processes the response. This
is how you crack custom auth flows.

### General pattern

```python
import re, httpx

def scan_bundles(page_url: str, search_terms: list[str]) -> dict:
    """Fetch a page, extract all JS bundle URLs, scan each for search terms."""
    with httpx.Client(http2=False, follow_redirects=True, timeout=30) as client:
        html = client.get(page_url).text

        # Extract all JS chunk URLs (Next.js / Turbopack pattern)
        js_urls = list(set(re.findall(
            r'["\'](/_next/static/[^"\' >]+\.js[^"\' >]*)', html
        )))

        results = {}
        for url in js_urls:
            js = client.get(f"{page_url.split('//')[0]}//{page_url.split('//')[1].split('/')[0]}{url}").text
            for term in search_terms:
                if term.lower() in js.lower():
                    # Extract context around the match
                    idx = js.lower().find(term.lower())
                    context = js[max(0, idx-100):idx+200]
                    results.setdefault(term, []).append({
                        "chunk": url[-40:],
                        "size": len(js),
                        "context": context,
                    })
        return results
```

### Config patterns to search for

| What | Search terms |
|---|---|
| API keys | `apiKey`, `api_key`, `X-Api-Key`, `widgetsApiKey` |
| GraphQL endpoints | `appsync-api`, `graphql` |
| Tenant / namespace | `host.split`, `subdomain` |
| Cognito credentials | `userPoolId`, `userPoolClientId` |
| Auth endpoints | `AuthFlow`, `InitiateAuth`, `cognito-idp` |

### Custom endpoint patterns to search for

| What | Search terms |
|---|---|
| Custom auth flows | `verify-otp`, `verify-code`, `verify-token`, `confirm-code` |
| Hidden API routes | `fetch(`, `/api/` |
| Token construction | `callback/email`, `hashedOtp`, `rawOtp`, `token=` |
| Form submission handlers | `submit`, `handleSubmit`, `onSubmit` |

### How we cracked Exa's custom OTP flow

Exa's login page uses a custom 6-digit OTP system built on top of NextAuth.
The standard NextAuth callback failed with `error=Verification`. Scanning
the JS bundles revealed the actual flow:

```python
# Search terms that found the hidden endpoint
results = scan_bundles("https://auth.exa.ai", ["verify-otp", "verify-code", "callback/email"])
```

In a 573KB chunk, this surfaced:
```javascript
fetch("/api/verify-otp", {method: "POST", headers: {"Content-Type": "application/json"},
  body: JSON.stringify({email: e.toLowerCase(), otp: r})})
// → response: {email, hashedOtp, rawOtp}
// → constructs: token = hashedOtp + ":" + rawOtp
// → redirects to: /api/auth/callback/email?token=...&email=...
```

This revealed the entire auth flow — custom endpoint, request/response shape,
and token construction — all from static JS analysis.

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

## Navigation API Interception

When JS bundle scanning reveals what endpoint gets called but not what happens
with the result (e.g. a client-side token construction), you need to see the
actual values the browser produces. The **Navigation API interceptor** is the
key technique.

### The problem

Client-side JS often does: fetch → process response → set `window.location.href`.
Once the navigation fires, the page is gone and you can't inspect the URL. Network
capture only catches the fetch, not the outbound navigation. And the processing
logic is buried in minified closures you can't easily call.

### The solution

Modern Chrome exposes the [Navigation API](https://developer.mozilla.org/en-US/docs/Web/API/Navigation_API).
You can intercept navigation attempts, capture the destination URL, and prevent
the actual navigation — all with a single `evaluate` call:

```
evaluate { script: "navigation.addEventListener('navigate', (e) => { window.__intercepted_nav_url = e.destination.url; e.preventDefault(); }); 'interceptor installed'" }
```

Then trigger the action (click a button, submit a form), and read the captured URL:

```
click { selector: "button#submit" }
evaluate { script: "window.__intercepted_nav_url" }
```

The URL contains whatever the client-side JS constructed — tokens, hashes,
callback parameters — fully assembled and ready to replay with HTTPX.

### When to use this

| Situation | Technique |
|-----------|-----------|
| Button click makes a `fetch()` call | Fetch interceptor (see 3-auth) |
| Button click causes a page navigation | Navigation API interceptor |
| Form does a native POST (page reloads) | Inspect the `<form>` action + inputs |
| JS constructs a URL and redirects | Navigation API interceptor |

### Real example: Exa OTP verification

The Exa auth page's "VERIFY CODE" button calls `/api/verify-otp`, gets back
`{hashedOtp, rawOtp}`, then does `window.location.href = callback_url_with_token`.
The Navigation API interceptor captured the full callback URL, revealing the
token format is `{bcrypt_hash}:{raw_code}`.

This technique turned a "Playwright required" flow into a fully HTTPX-replayable
one. See [NextAuth OTP flow](../3-auth/nextauth.md#step-2-codetoken-submission).

### Combining with fetch interception

For complete visibility, install both interceptors before triggering an action:

```javascript
// Capture all fetch calls AND navigations
window.__cap = { fetches: [], navigations: [] };

// Fetch interceptor
const origFetch = window.fetch;
window.fetch = async (...args) => {
  const r = await origFetch(...args);
  const c = r.clone();
  window.__cap.fetches.push({
    url: typeof args[0] === 'string' ? args[0] : args[0]?.url,
    status: r.status,
    body: (await c.text()).substring(0, 3000),
  });
  return r;
};

// Navigation interceptor
navigation.addEventListener('navigate', (e) => {
  window.__cap.navigations.push(e.destination.url);
  e.preventDefault();
});
```

Read everything after: `evaluate { script: "JSON.stringify(window.__cap)" }`

---

## Read the Source

When bundle scanning and interception give you the *what* but not the *why*,
go read the library's source code. This is especially valuable for
well-known frameworks (NextAuth, Supabase, Clerk, Auth0) where the source
is on GitHub.

### Why this matters

Minified bundle code tells you *what* the client does. The library source tells
you *what the server expects*. These are two halves of the same flow.

### Example: NextAuth email callback

Bundle scanning revealed Exa calls `/api/auth/callback/email?token=...`. But
what does the server do with that token? Reading the
[NextAuth callback source](https://github.com/nextauthjs/next-auth/blob/main/packages/core/src/lib/actions/callback/index.ts)
revealed the critical line:

```typescript
token: await createHash(`${paramToken}${secret}`)
```

The server SHA-256 hashes `token + NEXTAUTH_SECRET` and compares with the
database. This told us the token format must be stable and deterministic — it
can't be a random value. Combined with the Navigation API interception that
showed `token = hashedOtp:rawOtp`, we had the complete picture.

### When to read the source

| Signal | Action |
|--------|--------|
| Standard framework (NextAuth, Supabase, etc.) | Read the auth callback handler source |
| Custom error messages (e.g. `error=Verification`) | Search the library source for that error string |
| Token/hash format is unclear | Read the token verification logic |
| Framework does something "impossible" | The source always reveals how |

### Where to find it

```
NextAuth:   github.com/nextauthjs/next-auth/tree/main/packages/core/src
Supabase:   github.com/supabase/auth
Clerk:      github.com/clerk/javascript
Auth0:      github.com/auth0/nextjs-auth0
```

Search the repo for the endpoint path (e.g. `callback/email`) or error message
(e.g. `Verification`) to find the relevant handler quickly.

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
| `skills/exa/` | JS bundle scanning for custom `/api/verify-otp` endpoint + Navigation API interception for token format + reading NextAuth source for server-side verification logic | `exa.py`, [nextauth.md](../3-auth/nextauth.md) |
| `skills/goodreads/` | Next.js Apollo cache + AppSync GraphQL + JS bundle scanning | `public_graph.py` |
| `skills/austin-boulder-project/` | JS bundle config extraction (API key + namespace) | `abp.py` |
| `skills/claude/` | Session cookie capture via Playwright | `claude-login.py` |
