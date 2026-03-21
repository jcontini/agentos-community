# Amazon

Search **Amazon product results** without an API key. The default path is a normal anonymous retail search (`/s?k=…`). If you install a **cookie provider** and choose connection `web`, the same search runs with your Amazon session cookies (optional personalization).

## Connections

| Connection | When to use |
|------------|-------------|
| **public** | Default — no auth, works everywhere. |
| **web** | You are logged into Amazon in a browser the provider can read; pass `connection: "web"` on `search` for a signed-in view. |

`check_session` always uses **web** and is a quick sanity check that cookies still work.

## Tools

### `search`

- **params**: `query` (required), `limit` (optional, max 24), `connection` (`"public"` \| `"web"`).
- **params.url**: Optional full Amazon search/results URL. You rarely need this directly; the **`web_search`** capability passes it when URL routing selects this skill (e.g. `url` contains `amazon.com/...`).

### `check_session`

Fetches the account landing page and returns whether the title looks like a signed-in account page.

## `web_search` routing

This skill registers **`web_search`** with `urls:` patterns for major `amazon.*` hosts. If a client calls `web_search` with an `url` field matching those patterns, the runtime prefers **amazon** over generic providers. You can still force another skill with `skill: "exa"` (or similar).

## Limits

- Results are parsed from **HTML**; Amazon may change markup. Organic rows are preferred; sponsored blocks are skipped when marked `AdHolder`.
- **International sites**: `public` connection defaults to `https://www.amazon.com`. For other storefronts, pass a full `url` to the search operation (or extend `base_url` / add connections later).
- Requires **`httpx`** with HTTP/2 support (`pip install "httpx[http2]"`) for reliable responses.

## Official API note

**Product Advertising API** is the supported way to get structured product data at scale, but it needs AWS signing and an Associates account. This skill intentionally uses retail HTML for a zero-setup path.
