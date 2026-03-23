# Amazon

Search products, get details, and access your Amazon account. No API keys — uses Amazon's public autocomplete API and browser session cookies.

## Features

### Product Search
- **`search_suggestions`** — Keyword autocomplete via Amazon's public JSON API (completion.amazon.com). Up to 10 suggestions per query. Supports organic and personalized ranking, 21 marketplaces, 25+ department filters. Zero authentication, no bot detection.
- **`search_products`** — Full product search results with ASIN, title, price, rating, review count, images, and Prime badge. Parsed from search result HTML.
- **`get_product`** — Detailed product page data: title, price, brand, description, rating, images, categories, availability. Parsed from product detail HTML including Amazon's `a-state` embedded data.

### Order History (requires session cookies)
- **`list_orders`** — List orders with date, total, status, and items. Supports time filters: `last30`, `months-3`, `year-2024` through `year-2006`. Pagination via `page` parameter (10 per page).
- **`get_order`** — Full order details: per-item prices and quantities, order summary (subtotal, shipping, tax, grand total), shipping address, delivery status, and tracking URL.
- **`buy_again`** — Products Amazon recommends for repurchase. Returns ASIN, title, price, Prime eligibility.
- **`subscriptions`** — Active Subscribe & Save subscriptions with delivery frequency, next delivery date, upcoming scheduled deliveries, edit deadlines, and total savings.

### Account (requires session cookies)
- **`check_session`** — Verify your Amazon session is active and identify the logged-in account. Returns display name, customer ID, marketplace, and Prime status.

## Setup

### Public Operations (no setup needed)

`search_suggestions` works immediately — it hits Amazon's public autocomplete API with no authentication.

`search_products` and `get_product` parse public Amazon pages. They work without login but may occasionally encounter CAPTCHAs under heavy use.

### Authenticated Operations

1. Sign in to [amazon.com](https://www.amazon.com) in a browser whose cookies are visible to an installed cookie provider (Brave, Firefox, or Playwright)
2. The engine obtains `.amazon.com` cookies automatically — the full cookie jar is passed, including the auth-tier tokens (`at-main`, `sess-at-main`, `sst-main`) needed for account pages
3. Sessions last weeks to months

## Graph Model

| Entity | Represents | Key Fields |
|--------|------------|------------|
| **account** | Amazon account | customer_id, display, issuer, marketplace_id, is_prime |
| **order** | Purchase order | order_id, order_date, total, status, delivery_date, shipping_address, tracking_url, summary, items |
| **product** | Amazon product | asin, title, price, brand, rating, image, prime, availability |

### Relationships

```
Account --placed--> Order --contains--> Product
```

Orders contain nested product entities. Each product is identified by ASIN and linked to the order. When imported to the graph, orders are connected to the account and products are connected to the orders.

## Examples

```bash
# Autocomplete suggestions (public JSON API — most reliable)
run({ skill: "amazon", tool: "search_suggestions",
  params: { query: "wireless head" } })

# Full product search
run({ skill: "amazon", tool: "search_products",
  params: { query: "usb c cable", department: "electronics" } })

# Product details by ASIN
run({ skill: "amazon", tool: "get_product",
  params: { asin: "B0BQPNMXQV" } })

# Check session / identify account
run({ skill: "amazon", tool: "check_session" })

# List recent orders (default: last 30 days)
run({ skill: "amazon", tool: "list_orders" })

# List orders from past 3 months
run({ skill: "amazon", tool: "list_orders",
  params: { filter: "months-3" } })

# List orders from a specific year (supports 2006-2026)
run({ skill: "amazon", tool: "list_orders",
  params: { filter: "year-2024" } })

# Page 2 of results (10 per page)
run({ skill: "amazon", tool: "list_orders",
  params: { filter: "months-3", page: 2 } })

# Get full order details (items, prices, shipping, tracking)
run({ skill: "amazon", tool: "get_order",
  params: { order_id: "114-4501818-4961814" } })

# Products recommended for repurchase
run({ skill: "amazon", tool: "buy_again" })

# Subscribe & Save subscriptions
run({ skill: "amazon", tool: "subscriptions" })
```

## Cookie Architecture

Amazon uses tiered cookie-based authentication:

| Cookie | Purpose | Required For |
|--------|---------|-------------|
| `session-id`, `session-token`, `ubid-main` | Basic session | Browsing, search |
| `x-main` | "Remember me" persistence | Session continuity |
| `at-main` (`Atza\|...`) | Authentication token | Account pages, orders |
| `sess-at-main` | Session auth complement | Account pages, orders |
| `sst-main` (`Sst1\|...`) | SSO state token | Cross-service auth |
| `sso-state-main` (`Xdsso\|...`) | SSO state persistence | Cross-service auth |

The skill passes the cookie jar for `.amazon.com` with three cookies **excluded**: `csd-key`, `csm-hit`, and `aws-waf-token`. These trigger Amazon's Siege client-side decryption, rendering the HTML unparseable without JavaScript. All auth-tier tokens (`at-main`, `sess-at-main`, `sst-main`) are included.

## Technical Details

### Anti-Bot Considerations

- `search_suggestions` uses a separate domain (`completion.amazon.com`) with lighter bot detection
- `search_products` and `get_product` navigate to the homepage first to establish a session before fetching target pages
- Amazon's Lightsaber bot detection monitors client hints, session behavior, and fingerprinting
- Recommended: 2-3 second delays between HTML scraping requests
- If blocked, `search_suggestions` remains available as a reliable fallback

### Order History Page

The order history page is **pure server-rendered HTML** — no hidden JSON or GraphQL API exists for orders. The page uses `.order-card` containers with `li.order-header__header-list-item` elements for date, total, ship-to, and order ID, plus `.yohtmlc-item` containers for product line items.

**Siege encryption**: Amazon's `SiegeClientSideDecryption` encrypts order card contents when the `csd-key` cookie is present (signaling the client can decrypt via JS). The skill strips `csd-key`, `csm-hit`, and `aws-waf-token` from the cookie jar to force Amazon to serve plain, parseable HTML. Without this, the order cards are empty JS blobs.

**Selectors**: Amazon uses `<span dir="ltr">` (not `<bdi dir="ltr">`) for order IDs, and `li.order-header__header-list-item` for header fields. The `data-component` attributes from the amazon-orders library are not present in the HTML served to httpx clients.

### ASIN Format

10 uppercase alphanumeric characters: `/^[A-Z0-9]{10}$/`
- Non-book products start with `B0` (e.g. `B0BQPNMXQV`)
- Books use ISBN-10 (starts with digits)

### Page Architecture

Amazon uses a server-rendered monolith (not Next.js/React SSR). Product data is embedded in:
- Standard HTML DOM (title, price, rating selectors)
- `<script type="a-state">` proprietary state blocks (~35 per product page)
- `ImageBlockATF` inline scripts (full image manifests)
- Hidden form inputs (ASIN, merchant ID, CSRF tokens)

No JSON-LD or GraphQL endpoints are exposed publicly.

## Backlog

### Done
- [x] `search_suggestions` — public completion API
- [x] `search_products` — HTML search result parsing
- [x] `get_product` — product detail page parsing
- [x] `list_orders` — order history with BeautifulSoup + anti-bot headers
- [x] `check_session` / `whoami` — account identity extraction
- [x] Siege bypass — strip `csd-key` cookie to force plain HTML
- [x] `get_order` — full detail parsing with per-item prices, quantities, summary, tracking
- [x] Pagination — `page` parameter, 10 per page, next-page detection
- [x] Time filters — `last30`, `months-3`, `year-YYYY` back to 2006
- [x] `buy_again` — repurchase recommendations from `/gp/buyagain`
- [x] `subscriptions` — Subscribe & Save management via AJAX endpoint

### In Progress
(none)

### Planned
- [ ] Digital orders — Kindle, apps, etc.
- [ ] Payment method extraction from order details

### Known Issues
- Cookie provider freshness — stale cookies from inactive browsers override fresh ones (backlog `wcya9y`)
- Siege encryption — Amazon's `csd-key` cookie triggers client-side encrypted HTML; must be stripped
- Chrome version drift — `Sec-Ch-Ua` headers must match a real browser version; currently pinned to Chrome 145

## Limitations

- Always returns exactly 10 autocomplete suggestions (server-side cap, `limit` param is ignored)
- HTML scraping operations may be blocked by Amazon's bot detection under heavy use
- Amazon does not provide a public JSON API for product search or details
- Order history parsing relies on HTML structure which Amazon may change
- `csd-key` cookie must be stripped or Amazon sends Siege-encrypted content that requires JS to decrypt
