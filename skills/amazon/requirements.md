# Amazon Skill — Requirements & Research

## Goal

Search Amazon products and view order history. No official API keys. No paid services at small scale.

## Constraints

- No Amazon Product Advertising API (PA-API) — requires approval, has quotas
- No paid proxy/scraping services
- Small-scale personal use only (1-2 req/sec max)
- Session cookies already available via the skill's cookie provider

---

## Planned Operations

### Tier 1: Public, No Auth

| Operation | Source | Difficulty |
|-----------|--------|------------|
| `search_suggestions` | Autocomplete API (clean JSON) | Trivial |
| `search_products` | HTML parse `/s?k={query}` | Medium |
| `get_product` | HTML parse `/dp/{ASIN}` + `a-state` blocks | Medium |

### Tier 2: Authenticated (Session Cookies)

| Operation | Source | Difficulty |
|-----------|--------|------------|
| `list_orders` | HTML parse `/gp/your-account/order-history` | Medium |
| `get_order` | HTML parse `/gp/your-account/order-details?orderID={id}` | Medium |

---

## Research Findings

### 1. Autocomplete / Suggestions API

The star find. A public JSON API with zero authentication.

**Endpoint:**
```
GET https://completion.amazon.{tld}/api/2017/suggestions
```

**Required parameters:**

| Param | Description | Example |
|-------|-------------|---------|
| `mid` | Marketplace ID | `ATVPDKIKX0DER` (US) |
| `alias` | Department search index | `aps` (all products) |
| `prefix` | Search query (URL-encoded) | `wireless+headphones` |

**Optional parameters:**

| Param | Description | Notes |
|-------|-------------|-------|
| `suffix` | Text after cursor | Enables mid-query completion (e.g. `prefix=laptop&suffix=stand`) |
| `event` | UI trigger | `onFocusWithSearchTerm`, `onKeyPress` |
| `lop` | Locale | `en_US`, `en_GB`, `de_DE`, etc. |
| `session-id` | Session identifier | Enables personalized ranking (see below) |
| `page-type` | Page context | `Gateway`, `Detail`, `Search` |
| `site-variant` | Client variant | `desktop`, `mobile`, `touch` |
| `fb` | Feature bucket | `1` or `0` |
| `suggestion-type` | Type filter (repeatable) | `KEYWORD`, `WIDGET` |
| `client-info` | Client identifier | `search-ui` |

**`limit` parameter is accepted but ignored.** Always returns exactly 10 results.

**Personalized ranking:** When `session-id`, `lop`, `page-type`, and `site-variant` are all provided, the ranking strategy changes from `organic` to `p13n-expert-pd-ops-ranker` with `strategyApiType: "RANK"`.

**Response schema:**
```json
{
  "alias": "aps",
  "prefix": "wireless head",
  "suffix": null,
  "suggestions": [
    {
      "suggType": "KeywordSuggestion",
      "type": "KEYWORD",
      "value": "wireless headphones",
      "refTag": "nb_sb_ss_i_1_13",
      "candidateSources": "local",
      "strategyId": "organic",
      "prior": 0.0,
      "ghost": false,
      "help": false,
      "queryUnderstandingFeatures": [{ "source": "QU_TOOL", "annotations": [] }]
    }
  ],
  "responseId": "3RSYX5ON2LGNA",
  "shuffled": false
}
```

**`refTag` format:** `nb_sb_ss_{strategy}_{position}_{prefixLength}` where `nb`=navbar, `sb`=search bar, `ss`=search suggestion, and strategy is `i` (inline/organic), `sc` (spell-corrected), or the ranker name.

#### Marketplace IDs (Verified Live)

| Country | Domain | `mid` | Status |
|---------|--------|-------|--------|
| US | amazon.com | `ATVPDKIKX0DER` | Working |
| UK | amazon.co.uk | `A1F83G8C2ARO7P` | Working |
| DE | amazon.de | `A1PA6795UKMFR9` | Working |
| FR | amazon.fr | `A13V1IB3VIYBER` | Empty results |
| JP | amazon.co.jp | `A1VC38T7YXB528` | Working |
| CA | amazon.ca | `A2EUQ1WTGCTBG2` | Working |
| AU | amazon.com.au | `A39IBJ37TRP1C6` | Working |
| IN | amazon.in | `A21TJRUUN4KGV` | 502 (subdomain down) |
| ES | amazon.es | `A1RKKUPIHCS9HS` | Working |
| IT | amazon.it | `APJ6JRA9NG5V4` | Working |
| MX | amazon.com.mx | `A1AM78C64UM0Y8` | Working |
| BR | amazon.com.br | `A2Q3Y263D00KWC` | Working |
| NL | amazon.nl | `A1805IZSGTT6HS` | Working |
| SE | amazon.se | `A2NODRKZP88ZB9` | Working |
| PL | amazon.pl | `A1C3SOZLQLW3CS` | Empty results |
| SG | amazon.sg | `A19VAU5U5O7RUS` | Working |
| AE | amazon.ae | `A2VIGQ35RCS4UG` | Working |
| SA | amazon.sa | `A17E79C6D8DWNP` | Working |
| TR | amazon.com.tr | `A33AVAJ2PDY3EV` | Working |
| BE | amazon.com.be | `AMEN7PMS3EDWL` | Working |
| EG | amazon.eg | `ARBP9OOSHTCHU` | Working |

18 of 21 return results. FR and PL return valid JSON but empty suggestions. IN returns CloudFront 502.

#### Department Aliases (Verified on US)

| Alias | Department |
|-------|-----------|
| `aps` | All Products (default) |
| `electronics` | Electronics |
| `sporting` | Sports & Outdoors |
| `toys-and-games` | Toys & Games |
| `stripbooks` | Books |
| `fashion` | All Fashion |
| `fashion-womens` | Women's Fashion |
| `grocery` | Grocery & Gourmet Food |
| `beauty` | Beauty & Personal Care |
| `automotive` | Automotive |
| `garden` | Garden & Outdoor |
| `videogames` | Video Games |
| `tools` | Tools & Home Improvement |
| `baby-products` | Baby |
| `office-products` | Office Products |
| `pets` | Pet Supplies |
| `digital-music` | Digital Music |
| `appliances` | Appliances |

Additional known aliases (from search dropdown, not all tested): `instant-video`, `digital-text` (Kindle), `mobile-apps`, `software`, `hpc` (Health), `industrial`, `arts-crafts-sewing`, `collectibles`, `handmade`, `gift-cards`, `smart-home`, `luxury-beauty`, `fresh`, `audible`, `amazon-devices`, `fashion-mens`, `movies-tv`, `music`, `shoes`, `watches`, `jewelry`, `kitchen`.

Invalid aliases return empty suggestions with HTTP 200 (no error).

---

### 2. Page Architecture

Amazon does **not** use Next.js, Apollo, GraphQL, or any modern SPA framework. It is a **server-rendered monolith** with progressive client-side enhancement.

#### Custom State System: `<script type="a-state">`

Amazon's proprietary client-state injection. ~35 state blocks per product page.

| State Key | Contents |
|-----------|----------|
| `oas-offer-refresh-page-state` | Marketplace ID, `data.amazon.com` endpoint, CSRF token |
| `turbo-checkout-page-state` | Buy-now config, ASIN, session, CSRF tokens |
| `desktop-twister-sort-filter-data` | Product variation data (colors, sizes, ASINs per variant, ~5.5KB) |
| `social-proofing-page-state` | ASIN, merchant ID, `isRobot` bot detection flag |
| `acState` | Current ASIN |

#### No JSON-LD

Amazon does not embed `schema.org/Product` structured data on any page. Unusual for a major retailer.

#### `ImageBlockATF` Inline Script

Product images with hiRes, thumb, large, and main variants at multiple sizes, registered via Amazon's `P` module loader.

#### Module System

Custom AMD-like `P` module (`AmazonUIPageJS`). Components register via `P.when('dep').register('name', fn)`. Rush framework for client-side navigation.

---

### 3. Search Results — DOM Structure

Container: `.s-main-slot.s-result-list.s-search-results`

Each result: `[data-component-type="s-search-result"]`

| Element | Selector |
|---------|----------|
| Product with ASIN | `[data-asin]:not([data-asin=""])` |
| Title | `h2 a span` or `h2 span.a-text-normal` |
| Price | `.a-price .a-offscreen` |
| Rating | `.a-icon-alt` (e.g. "4.3 out of 5 stars") |
| Review count | `span.s-underline-text` (e.g. "(35.9K)") |
| Image | `img.s-image` |
| Prime badge | `[aria-label="Amazon Prime"]` |
| Sponsored | `.AdHolder` class |

Data attributes per result: `data-asin`, `data-index`, `data-uuid`, `data-cel-widget`.

---

### 4. Product Detail Page — DOM Selectors

| Data Point | Selector |
|------------|----------|
| Title | `#productTitle` |
| Price | `.a-price .a-offscreen` or `#corePrice_feature_div .a-offscreen` |
| Rating | `#acrPopover .a-icon-alt` |
| Review count | `#acrCustomerReviewText` |
| ASIN | `#ASIN` or `input[name="ASIN"]` |
| Brand | `#bylineInfo` |
| Availability | `#availability span` |
| Main image | `#landingImage` |
| Breadcrumbs | `#wayfinding-breadcrumbs_feature_div li a` |
| Canonical URL | `link[rel="canonical"]` |

Hidden inputs: `ASIN`, `merchantID`, `session-id`, `anti-csrftoken-a2z`, `offerListingID`.

---

### 5. ASIN Format

- 10 uppercase alphanumeric characters: `/^[A-Z0-9]{10}$/`
- Non-book products start with `B0` (e.g. `B0BQPNMXQV`)
- Books use ISBN-10 (starts with digits, e.g. `0062868373`)
- Found in: `data-asin` attribute, `#ASIN` hidden input, URL `/dp/{ASIN}`, `a-state` scripts, canonical URL

---

### 6. Anti-Bot Detection

Amazon's bot detection stack:

| System | Purpose |
|--------|---------|
| **Lightsaber** | Main bot detection framework |
| **Vowels** | Timing/fingerprinting challenges via metrics image fetch |
| **FWCIM** | FingerPrint Web Client Identification Module |
| **BotCXPolicy** | Bot classification policy (returns 429 when triggered) |

Signals checked: client hint headers (`sec-ch-device-memory`, `sec-ch-dpr`, `sec-ch-viewport-width`), `isRobot` flag in `a-state`, session behavior.

**Mitigations for small-scale use:**
- Navigate to homepage first, then to search (direct search URL triggers "dog page")
- Use browser cookies from a real session
- 2-3 second delays between requests
- Realistic User-Agent string
- The autocomplete API has lighter detection than the main site

---

### 7. Mobile View

**No advantage.** Amazon uses responsive design — one codebase, CSS media queries. Mobile UA gets identical HTML, same selectors, same `a-state` blocks. Mobile UA may actually be more suspicious (most real mobile users use the Amazon app). Legacy mobile paths (`/gp/aw/`) redirect to standard pages.

---

### 8. Hidden Catalog API

`data.amazon.com/api/catalog/v1/items` exists and returns `application/vnd.com.amazon.api+json` errors referencing `api.amazon.com/shop`. Requires authentication of an unknown token format. Not viable without further reverse engineering and unlikely to yield more than the autocomplete API + HTML parsing approach.

---

### 9. Order History (Authenticated)

- **List orders:** `GET /gp/your-account/order-history` (HTML, requires session cookies)
- **Filter by year:** `?orderFilter=year-{YYYY}` or `last30`, `months-6`
- **Order details:** `GET /gp/your-account/order-details?orderID={id}`
- Without valid cookies: 302 redirect to OpenID sign-in
- Same HTML regardless of UA (responsive design)

---

### 10. Existing Open-Source Reference

| Repo | Stars | Approach | Notes |
|------|-------|----------|-------|
| tducret/amazon-scraper-python | 881 | requests + BS4, CSS selectors | Multiple selector sets for layout variants |
| sushil-rgb/AmazonMe | 67 | aiohttp + BS4, async | Supports 12 countries, rotating proxies |
| tobiasmcnulty/amzscraper | 50 | Selenium for order history | Login-based; our cookie approach is better |

---

### 11. Wishlists / Lists (Authenticated)

Your Lists page: `GET /hz/wishlist/ls` — requires session cookies. Shows all user lists with a left nav and item view.

#### Page Structure

- **Container:** `#wishlist-page` with tab navigation (`#my-lists-tab`, `#friends-tab`)
- **Left nav:** `#your-lists-nav` contains all user lists as `.wl-list` entries
- **Content area:** `#content-right` shows the currently selected list's items
- **Hidden input:** `#listId` holds the current list's external ID

#### Left Nav — List of Lists

Each list entry in the left nav:

| Element | Selector |
|---------|----------|
| List link | `a[id^="wl-list-link-"]` — href is `/hz/wishlist/ls/{LIST_ID}` |
| List name | `.wl-list-entry-title span[id^="wl-list-entry-title-"]` |
| Default label | `#list-default-collaborator-label` (only on default list, text "Default List") |
| Privacy | `.wl-list-entry-privacy span` (e.g. "Public", "Private") |
| Selected state | `.wl-list.selected` class on the container |

The list ID is an alphanumeric string like `OCYU5PINQ1B7`, embedded in the link's `id` attribute and `href`.

#### `a-state` Blocks (Structured Data)

| State Key | Contents |
|-----------|----------|
| `pageInfo` | `listExternalId`, `listType` ("wishlist"), `sid`, `countryCode`, `customerId`, `filter`, `sort`, `viewType`, `numberOfItemsBeforeCF` |
| `viewState` | `filter` ("unpurchased"), `sort` ("date-added"), `page`, `viewType` ("list"), `store` |
| `scrollState` | `showMoreUrl` (AJAX pagination endpoint), `paginationToken`, `itemsRenderedSoFar` |
| `rememberState` | `listId`, `listType` ("WishList"), `isSharedWL` |

#### List Item DOM — `<li class="g-item-sortable">`

Data attributes on each `<li>`:

| Attribute | Value |
|-----------|-------|
| `data-id` | List ID (e.g. "OCYU5PINQ1B7") |
| `data-itemid` | Item ID (e.g. "I2O54JU3IOWCUH") |
| `data-price` | Price as string (e.g. "14.99") |
| `data-reposition-action-params` | JSON with `itemExternalId` ("ASIN:0316129445\|ATVPDKIKX0DER"), `listType`, `sid` |

Inner selectors:

| Data Point | Selector |
|------------|----------|
| Title & product link | `a[id^="itemName_"]` — `title` attr has name, `href` has `/dp/{ASIN}/` |
| Image | `#itemImage_{ITEM_ID} img` |
| Byline (author/format) | `span[id^="item-byline-"]` (e.g. "by Andrew Weil MD (Hardcover)") |
| Price | `.price-section .a-price .a-offscreen` (e.g. "$14.99") |
| Rating | `.a-icon-star-small span.a-icon-alt` (e.g. "4.5 out of 5 stars") |
| Review count | `a[id^="review_count_"]` |
| Comment | `span[id^="itemComment_"]` |
| Priority | `span[id^="itemPriorityLabel_"]` (e.g. "medium") |
| Quantity needed | `span[id^="itemRequested_"]` |
| Quantity purchased | `span[id^="itemPurchased_"]` |
| Date added | `span[id^="itemAddedDate_"]` (e.g. "Item added December 21, 2011") |
| Price drop | `span[id^="itemPriceDrop_"]` + sibling span with original price |

ASIN extraction: from `data-reposition-action-params` JSON field `itemExternalId` (format `ASIN:{ASIN}|{MARKETPLACE_ID}`), or regex from the product link href `/dp/{ASIN}/`.

#### Pagination — Token-Based AJAX

Items load 10 at a time. Additional items are fetched via the `showMoreUrl` from the `scrollState` a-state block:

```
GET /hz/wishlist/slv/items?filter=unpurchased&paginationToken={TOKEN}&itemsLayout=LIST&sort=purchase-date-added&type=wishlist&lid={LIST_ID}
```

Returns HTML fragments appended to `#g-items`. The response likely contains updated `scrollState` with the next `paginationToken` for continued pagination. Requires `X-Requested-With: XMLHttpRequest` and `Referer` headers (following the AJAX pattern from subscriptions).

#### List Settings

Manage list modal: `GET /hz/wishlist/settings/{LIST_ID}?type=WishList&ajax=true` — returns list configuration (name, privacy, type). The list type is stored as `WishList` (capital W, capital L).

---

## Implementation Priority

1. **`search_suggestions`** — Autocomplete API. Trivial. Clean JSON. Start here.
2. **`search_products`** — HTML parse search results. Medium. Selectors well-documented.
3. **`get_product`** — HTML parse product page + `a-state` extraction. Medium. Rich data.
4. **`list_orders`** — HTML parse order history with session cookies. Medium. Auth infra exists.
5. **`get_order`** — HTML parse order detail page. Medium. Depends on `list_orders`.
6. **`list_lists`** — HTML parse left nav of `/hz/wishlist/ls`. Easy. Auth infra exists.
7. **`get_list`** — HTML parse list items from `/hz/wishlist/ls/{LIST_ID}`. Medium. Token-based pagination.
