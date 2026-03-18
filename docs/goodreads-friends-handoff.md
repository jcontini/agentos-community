# Handoff: Goodreads Friends via HTML + Cookies

## The Problem

Goodreads friends are **not available through GraphQL**. The AppSync backend does not expose a friends query — `getViewer` returns null even with session cookies, and JWT cookies don't authenticate AppSync cross-origin. Friends are only accessible from the legacy HTML pages, which require authenticated cookies.

## What Works

| Approach | Details |
|----------|---------|
| **Desktop HTML** | `https://www.goodreads.com/friend?ref=nav_profile_friends` — 30 friends per page |
| **Session cookies** | Same cookies from the browser (e.g. via `curl -b`) authenticate the request |
| **Cookies used** | `session-id`, `at-main`, `sess-at-main`, `_session_id2`, `session-token`, `x-main`, `ubid-main`, … |
| **HTML parsing** | `friendContainer` divs with `href="/user/show/(\d+)"` and display name |
| **httpx script** | `scripts/fetch_friends_httpx.py` — fetches friends with cookies, parses HTML |
| **Playwright login** | Can log in; use `clear_cookies` first to reach the login form |
| **Cookie extraction** | Playwright `cookies { domain: ".goodreads.com" }` after login |

## What Doesn't Work

| Approach | Issue |
|----------|-------|
| **AppSync / GraphQL** | `getViewer` is null; friends are not on the GraphQL surface |
| **JWT cookie** | `jwt_token` cookie does not authenticate AppSync |
| **Cross-origin cookies** | `.goodreads.com` cookies don't get sent to `appsync-api.amazonaws.com` |
| **Mobile JSON** | `format=json&mobile_xhr=1` exists but only returns 15 per page |
| **Unauthenticated** | `/friend` redirects to sign-up if no cookies |

## Current `list_friends` Operation

The `readme.md` operation uses `rest:` with unauthenticated HTML scraping against `/friend/user/{user_id}`. This works for public friend lists but may fail for private profiles or profiles that gate their friends list. It does not use `connection: web` for cookie auth.

## Recommended Implementation

Use Playwright to log in, then scrape the desktop friends page as HTML (not GraphQL, not mobile JSON):

1. **Log in** via Playwright (email or Amazon SSO).
2. **Navigate** to `/friend?ref=nav_profile_friends`.
3. **Extract cookies** from the Playwright context with `cookies { domain: ".goodreads.com" }`.
4. **Fetch pages** — either:
   - **(A)** Hand cookies to httpx/direct HTTP and fetch `/friend?page=N` server-side, or
   - **(B)** Scrape the page DOM directly in Playwright with `read_webpage` / `evaluate`.
5. **Parse** `friendContainer` divs for `user/show/(\d+)` and display name.
6. **Paginate** with `?page=2`, `?page=3`, etc. (30 friends per page).

Option A is preferred for production — it avoids keeping the browser open during pagination and is faster for large friend lists. Option B is simpler for a first pass.

## Relevant Files

| File | Purpose |
|------|---------|
| `skills/goodreads/scripts/fetch_friends_httpx.py` | httpx flow: cookie loading, HTML/JSON parsing, CSRF extraction, pagination stub |
| `skills/goodreads/scripts/test_authenticated_graphql.py` | Confirms GraphQL does NOT work for friends (getViewer is null) |
| `skills/goodreads/public_graph.py` | GraphQL helpers — not used for friends |
| `skills/goodreads/readme.md` | Skill definition; `list_friends` operation (currently unauthenticated REST) |
| `skills/playwright/readme.md` | Login, `cookies`, `clear_cookies`, `capture_network` |

## Open Questions

1. **Should `list_friends` switch to `connection: web`?** Currently it declares `connection: graphql` but uses `rest:`. If friends always need cookies, it should use the `web` connection.
2. **Pagination in the skill operation** — the current `list_friends` takes a `page` param but only fetches one page. An `all_friends` helper that auto-paginates would be more useful for the agent.
3. **Cookie refresh** — Goodreads session cookies expire. The skill needs a story for re-auth (Playwright login flow or passive cookie provider like `brave-browser`/`firefox`).
4. **Rate limiting** — 30 friends per page means a user with 300 friends needs 10 requests. A 1-2 second delay between pages is prudent.

## Key Insight

Friends are only available from HTML, not GraphQL. Desktop HTML is preferred (30 vs 15 per page). Playwright should be used to log in; then either scrape the page in Playwright or hand cookies off to httpx for server-side fetching.
