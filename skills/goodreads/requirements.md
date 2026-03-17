# Goodreads Reverse-Engineering Requirements

This document captures the current reverse-engineering findings for Goodreads' modern web stack and data surfaces. It is a handoff artifact for future work in this skill folder.

## Current Architecture

Goodreads' modern site is a combination of:

- `Next.js` for page rendering and hydration
- `Apollo Client` for browser-side GraphQL state and normalized cache storage
- AWS `AppSync` for the GraphQL backend
- Goodreads web session cookies for logged-in account context

These layers matter because Goodreads does not expose one single public API surface anymore. Public data comes from a mix of page hydration and browser-visible GraphQL traffic.

## How The Page Layer Works

Public Goodreads book pages render server-side HTML and include a `script#__NEXT_DATA__` payload. That payload contains `props.pageProps`, and `pageProps` often contains `apolloState`.

`apolloState` is a serialized Apollo normalized cache. It is one of the most useful data sources because it already contains structured entity data that the page needs to render. This avoids scraping visible HTML for many book-level fields.

Important structure:

- `__NEXT_DATA__`
- `__NEXT_DATA__.props.pageProps`
- `__NEXT_DATA__.props.pageProps.apolloState`
- `apolloState.ROOT_QUERY`

The current implementation reads that data in `public_graph.py`:

```python
next_data = extract_next_data(html)
page_props = next_data.get("props", {}).get("pageProps", {})
apollo = page_props.get("apolloState", {})
root_query = apollo.get("ROOT_QUERY", {})
```

## How Apollo Works On Goodreads

Apollo stores GraphQL results in a normalized cache keyed by object references. Goodreads serializes that cache into the page payload.

Important patterns inside the cache:

- `ROOT_QUERY` contains top-level query entries
- entity references look like `Book:...`, `User:...`, `Review:...`
- query results often resolve to `{"__ref": "Book:..."}` style pointers

This means the public book page often already contains:

- the main book object
- work details
- work stats
- contributor references
- genre edges
- social signal summaries

The current extractor resolves the public book by legacy Goodreads ID using:

- `getBookByLegacyId({"legacyId":"<book_id>"})`

and then dereferences related Apollo objects from there.

## How AppSync Works Here

Goodreads uses an AWS AppSync GraphQL backend. AppSync is AWS's managed GraphQL service. The frontend sends GraphQL `POST` requests to an AppSync endpoint and includes a public `x-api-key`.

Known current endpoint:

- `https://kxbwmqov6jgg3daaamb744ycu4.appsync-api.us-east-1.amazonaws.com/graphql`

Known current public API key:

- `da2-xpgsdydkbregjhpr6ejzqdhuwy`

Current request shape:

- method: `POST`
- content type: `application/json`
- body: `{"query":"...","variables":{...}}`
- header: `x-api-key: <public key>`

This is implemented in `skills/goodreads/public_graph.py`.

## What The Public API Key Means

The AppSync key is public frontend configuration, not a user secret. It appears to grant anonymous client access to the Goodreads GraphQL backend for a subset of operations and fields.

It does not provide viewer identity.

It does not replace Goodreads login.

It does not unlock viewer-specific fields.

This is why some GraphQL calls succeed publicly while certain fields on those same object types return authorization errors.

## Public vs Authenticated Boundary

The key boundary observed so far is:

- page hydration and some GraphQL operations are public
- viewer-specific fields are not public
- Goodreads account context depends on Goodreads cookies

Examples of fields that were not publicly accessible in GraphQL responses:

- `viewerHasLiked`
- `viewerRelationshipStatus`

Those fields caused GraphQL authorization errors and had to be removed from the public review query.

This shows that Goodreads uses field-level authorization inside AppSync rather than simply blocking the whole endpoint.

## Goodreads Web Authentication

Logged-in Goodreads access is cookie-based on the web side.

Cookies already referenced by the skill:

- `session_id`
- `__Secure-user_session`

These cookies are separate from the public AppSync API key. The current understanding is:

- the public AppSync key identifies the frontend client
- Goodreads cookies identify the viewer session

Those are different auth layers serving different purposes.

## Public Resources Confirmed So Far

### Public Book Resource

The public book page contains enough structured data to resolve a rich book entity without replaying GraphQL for the main book itself.

Fields currently resolved from public page hydration include:

- book title
- description
- cover image
- primary contributor
- secondary contributors
- ISBN
- ISBN13
- publication date
- average rating
- ratings count
- review count
- page count
- publisher
- format
- language
- series
- genres
- places
- characters
- awards won
- Goodreads web URLs

The main book reference is currently found from:

- `ROOT_QUERY["getBookByLegacyId({\"legacyId\":\"<book_id>\"})"]`

### Public Social Signals

Some social counts are already present in the Apollo cache on the public book page.

Observed public cache key:

- `getSocialSignals({"bookId":"<internal book id>","shelfStatus":["CURRENTLY_READING","TO_READ"]})`

This has been used to read:

- `CURRENTLY_READING`
- `TO_READ`

### Public Reviews

Public reviews work through the AppSync GraphQL backend using `getReviews`.

Current query shape:

- operation: `getReviews`
- filter: `resourceType: "WORK"`
- filter: `resourceId: <internal work id>`
- pagination: `limit`

Publicly working review fields currently include:

- review text
- review timestamps
- rating
- like count
- comment count
- shelf metadata
- tags
- review URL
- reviewer name
- reviewer URL
- reviewer image
- reviewer follower count
- reviewer text review count

### Public Similar Books

Public similar books work through the AppSync GraphQL backend using `getSimilarBooks`.

Current query shape:

- operation: `getSimilarBooks`
- input ID: Goodreads internal book ID
- pagination: `limit`

Working fields include:

- title
- cover image
- web URL
- primary contributor name
- average rating
- ratings count

## How The Endpoint And Key Were Found

The AppSync endpoint and public API key were found from Goodreads' live frontend behavior, not from official docs.

The discovery path was:

- inspect Goodreads pages in a browser
- capture network traffic on public book pages
- inspect JavaScript/frontend state for GraphQL and AppSync references
- replay the discovered GraphQL requests directly outside the browser

The reverse-engineering patterns that proved useful are documented in `docs/reverse-engineering/` (1-transport, 2-discovery, 3-auth).

The most important discovery sequence is:

- look at `script#__NEXT_DATA__`
- inspect `pageProps.apolloState`
- capture GraphQL/AppSync traffic
- move to direct HTTP replay once the contract is known

## How GraphQL Access Behaves

Public AppSync access currently behaves like this:

- the endpoint is reachable anonymously
- requests work with `x-api-key`
- GraphQL documents can be replayed from Python or `curl`
- some fields are public
- some fields are blocked at the field level
- authorization errors are returned as GraphQL errors, not necessarily HTTP auth failures

That means a response like:

- `Not Authorized to access viewerHasLiked on type Review`

usually indicates:

- the endpoint is valid
- the operation is valid
- the blocked field is viewer-scoped

## Runtime Discovery Architecture

The AppSync endpoint and API key are **not hardcoded as the primary path**. Instead, `public_graph.py` discovers them at runtime using a three-tier strategy:

### Tier 1: Cache (instant)

A local `.runtime-cache.json` file stores the last discovered config with a 1-hour TTL. Subsequent calls within that window are instant.

### Tier 2: JS Bundle Extraction (~1-2 seconds)

Goodreads' Next.js `_app` chunk ships all environment configs as inline JSON:

```
"graphql":{"apiKey":"da2-...","endpoint":"https://....appsync-api.us-east-1.amazonaws.com/graphql","region":"us-east-1"}
```

Four environments are present: Dev, Beta, Preprod, Prod. Each has a `shortName` field. The discovery function fetches the `_app` chunk URL from the page HTML, downloads it, and extracts the Prod config.

This works because:
- the HTML page we already fetch for `__NEXT_DATA__` contains the bundle URLs
- the `_app` chunk URL changes hash on each deploy but the pattern is stable
- no browser or headless automation is needed

### Tier 3: Browser Network Capture (~15-20 seconds)

If JS bundle extraction fails (Goodreads changes their build output), a stealth headless Playwright browser loads a book page and captures AppSync requests from the network. This requires anti-bot settings (custom user agent, viewport, webdriver override) because Goodreads returns 403 to default headless Chromium.

### Tier 4: Hardcoded Fallback (last resort)

If all discovery fails, known-good values are used. These are labeled `hardcoded_fallback` in the runtime source field so callers can detect staleness.

### Why This Architecture

The stable concept is: Goodreads exposes AppSync config to the browser. The unstable details are the exact hostname and API key. This discovery chain means the skill self-heals when Goodreads rotates keys or changes endpoints, without requiring code changes.

## Known Files In This Folder

Primary implementation:

- `skills/goodreads/public_graph.py` — all public data operations and runtime discovery

Primary skill definition:

- `skills/goodreads/readme.md`

## Current Direct HTTP Behavior

The Python implementation uses direct HTTP with:

- browser-like `User-Agent`
- HTML fetch retries with exponential backoff
- GraphQL retries
- backoff on transient errors such as `429`, `500`, `502`, `503`, and `504`

## Current Proven Data Paths

These paths are proven and tested:

- public book details from `__NEXT_DATA__` and Apollo cache
- public review lists from AppSync `getReviews`
- public similar books from AppSync `getSimilarBooks`
- public social signal counts from Apollo cache `getSocialSignals(...)`
- public user profiles from HTML scraping
- public author profiles and book lists from HTML scraping
- AppSync config discovery from Next.js `_app` JS bundle

## Short Mental Model

- `Next.js` ships a hydrated page with `__NEXT_DATA__` containing Apollo cache
- `Apollo` stores structured entity data in the page payload
- `AppSync` serves additional GraphQL connections and slices
- the public `x-api-key` identifies the frontend client (discovered from JS bundle)
- Goodreads cookies identify the logged-in user

That is the current state of how Goodreads appears to work from the outside.
