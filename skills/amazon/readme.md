# Amazon

Search products, get details, and access your Amazon account. No API keys — uses Amazon's public autocomplete API and browser session cookies.

## Features

### Product Search
- **`search_suggestions`** — Keyword autocomplete via Amazon's public JSON API (completion.amazon.com). Up to 10 suggestions per query. Supports organic and personalized ranking, 21 marketplaces, 25+ department filters. Zero authentication, no bot detection.
- **`search_products`** — Full product search results with ASIN, title, price, rating, review count, images, and Prime badge. Parsed from search result HTML.
- **`get_product`** — Detailed product page data: title, price, brand, description, rating, images, categories, availability. Parsed from product detail HTML including Amazon's `a-state` embedded data.

### Account (requires session cookies)
- **`check_session`** — Verify your Amazon session is active

## Setup

### Public Operations (no setup needed)

`search_suggestions` works immediately — it hits Amazon's public autocomplete API with no authentication.

`search_products` and `get_product` parse public Amazon pages. They work without login but may occasionally encounter CAPTCHAs under heavy use.

### Authenticated Operations

1. Sign in to [amazon.com](https://www.amazon.com) in a browser whose cookies are visible to an installed cookie provider
2. The engine obtains `.amazon.com` cookies automatically
3. Sessions last weeks to months

## Examples

```bash
# Autocomplete suggestions (public JSON API — most reliable)
run({ skill: "amazon", tool: "search_suggestions",
  params: { query: "wireless head" } })

# Suggestions in a specific department
run({ skill: "amazon", tool: "search_suggestions",
  params: { query: "protein", department: "grocery" } })

# Personalized ranking
run({ skill: "amazon", tool: "search_suggestions",
  params: { query: "laptop", personalized: true } })

# Different marketplace
run({ skill: "amazon", tool: "search_suggestions",
  params: { query: "headphones", marketplace: "UK" } })

# Full product search
run({ skill: "amazon", tool: "search_products",
  params: { query: "usb c cable", department: "electronics" } })

# Product details by ASIN
run({ skill: "amazon", tool: "get_product",
  params: { asin: "B0BQPNMXQV" } })

# Check session
run({ skill: "amazon", tool: "check_session" })
```

## Data Model

| Entity | Represents | Key Fields |
|--------|------------|------------|
| **result** | Search keyword suggestion | value, search_url, strategy, department, marketplace |
| **product** | Amazon product | asin, title, price, brand, rating, ratings_count, image, prime, availability, categories |

## Autocomplete API Reference

The search suggestions endpoint is Amazon's public autocomplete API — clean JSON, no auth, no scraping.

**Endpoint:** `GET https://completion.amazon.{tld}/api/2017/suggestions`

### Marketplaces

| Code | Domain | Status |
|------|--------|--------|
| US | amazon.com | Working |
| UK | amazon.co.uk | Working |
| DE | amazon.de | Working |
| JP | amazon.co.jp | Working |
| CA | amazon.ca | Working |
| AU | amazon.com.au | Working |
| ES | amazon.es | Working |
| IT | amazon.it | Working |
| MX | amazon.com.mx | Working |
| BR | amazon.com.br | Working |
| NL | amazon.nl | Working |
| SE | amazon.se | Working |
| SG | amazon.sg | Working |
| AE | amazon.ae | Working |
| SA | amazon.sa | Working |
| TR | amazon.com.tr | Working |
| BE | amazon.com.be | Working |
| EG | amazon.eg | Working |
| FR | amazon.fr | Empty results |
| PL | amazon.pl | Empty results |
| IN | amazon.in | 502 |

### Departments

`all` (default), `electronics`, `books`, `sports`, `toys`, `fashion`, `grocery`, `beauty`, `automotive`, `garden`, `videogames`, `tools`, `baby`, `office`, `pets`, `music`, `appliances`, `kitchen`, `movies`, `software`, `health`, `jewelry`, `watches`, `shoes`, `industrial`, `arts`, `smart-home`, `kindle`

Invalid aliases silently return empty results (no errors).

### Ranking Strategies

- **Organic** (default) — `strategyId: "organic"`. Standard keyword suggestions.
- **Personalized** (`personalized: true`) — `strategyId: "p13n-expert-pd-ops-ranker"`. Uses population-level signals for ranking. Different suggestion order and sometimes different keywords.

## Technical Details

### Anti-Bot Considerations

- `search_suggestions` uses a separate domain (`completion.amazon.com`) with lighter bot detection
- `search_products` and `get_product` navigate to the homepage first to establish a session before fetching target pages
- Amazon's Lightsaber bot detection monitors client hints, session behavior, and fingerprinting
- Recommended: 2-3 second delays between HTML scraping requests
- If blocked, `search_suggestions` remains available as a reliable fallback

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

## Limitations

- Always returns exactly 10 autocomplete suggestions (server-side cap, `limit` param is ignored)
- HTML scraping operations may be blocked by Amazon's bot detection under heavy use
- Amazon does not provide a public JSON API for product search or details
- Order history requires authenticated session cookies (coming soon)
