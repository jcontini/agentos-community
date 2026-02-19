---
id: logo-dev
name: Logo.dev
description: Company logos via CDN - lookup by domain, ticker, or name
icon: icon.svg
color: "#635BFF"

website: https://www.logo.dev
privacy_url: https://www.logo.dev/privacy
terms_url: https://www.logo.dev/terms

auth:
  type: api_key
  label: Publishable Key
  help_url: https://www.logo.dev/dashboard

connects_to: logo-dev

adapters:
  image:
    terminology: Logo
    mapping:
      id: .path
      url: .url
      alt: .name
      size: .size
      format: '.mime_type | split("/") | .[1]'

seed:
  - id: logo-dev
    types: [software]
    name: Logo.dev
    data:
      software_type: api
      url: https://logo.dev
      launched: "2024"
      platforms: [api]
      pricing: freemium
    relationships:
      - role: offered_by
        to: simple-casual

  - id: simple-casual
    types: [organization]
    name: Simple Casual, LLC
    data:
      type: company
      url: https://logo.dev
      founded: "2024"

instructions: |
  Logo.dev returns company logos as images via CDN URLs.
  
  URL format: https://img.logo.dev/{identifier}?token=KEY&params
  
  Parameters:
  - size: 16-800 (default 128)
  - format: jpg, png, webp (svg enterprise only)
  - theme: auto, light, dark
  - greyscale: true/false
  - retina: true/false (doubles resolution)
  - fallback: monogram (default) or 404
  
  Lookup modes:
  - Domain: shopify.com
  - Ticker: ticker:AAPL
  - Crypto: crypto:BTC
  - Name: name:Shopify
  - ISIN: isin:US0378331005

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES - URL generators (Logo.dev is a CDN, not a JSON API)
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  # Download logo to A: drive
  download_logo:
    description: "Download company logo to A: drive. Returns image entity."
    params:
      domain: { type: string, required: true, description: "Domain (e.g., shopify.com)" }
      size: { type: integer, default: 128, description: "Size in pixels (16-800)" }
      format: { type: string, default: "png", description: "Image format (jpg, png, webp)" }
      dest: { type: string, description: "Destination path in A: drive (default: icons/{domain}.{format})" }
    returns: image
    download:
      url: '"https://img.logo.dev/" + .params.domain + "?token=" + .auth.key + "&size=" + ((.params.size // 128) | tostring) + "&format=" + (.params.format // "png")'
      path: '(.params.dest // ("icons/" + .params.domain + "." + (.params.format // "png")))'

  # Generate a logo URL for a domain
  logo_url:
    description: Generate CDN URL for a company logo by domain
    params:
      domain: { type: string, required: true, description: "Domain (e.g., shopify.com)" }
      size: { type: integer, default: 128, description: "Size in pixels (16-800)" }
      format: { type: string, default: "png", description: "Image format (jpg, png, webp)" }
      theme: { type: string, default: "auto", description: "Theme (auto, light, dark)" }
    returns: void
    rest:
      method: GET
      url: '"https://img.logo.dev/" + .params.domain + "?token=" + .auth.key + "&size=" + ((.params.size // 128) | tostring) + "&format=" + (.params.format // "png") + "&theme=" + (.params.theme // "auto")'
      response:
        raw: true

  # Generate a logo URL for a stock ticker
  ticker_url:
    description: Generate CDN URL for a company logo by stock ticker
    params:
      ticker: { type: string, required: true, description: "Stock ticker (e.g., AAPL)" }
      size: { type: integer, default: 128, description: "Size in pixels" }
      format: { type: string, default: "png", description: "Image format" }
    returns: void
    rest:
      method: GET
      url: '"https://img.logo.dev/ticker:" + .params.ticker + "?token=" + .auth.key + "&size=" + ((.params.size // 128) | tostring) + "&format=" + (.params.format // "png")'
      response:
        raw: true

  # Generate a logo URL by company name
  name_url:
    description: Generate CDN URL for a company logo by name
    params:
      name: { type: string, required: true, description: "Company name (e.g., Shopify)" }
      size: { type: integer, default: 128, description: "Size in pixels" }
      format: { type: string, default: "png", description: "Image format" }
    returns: void
    rest:
      method: GET
      url: '"https://img.logo.dev/name:" + (.params.name | @uri) + "?token=" + .auth.key + "&size=" + ((.params.size // 128) | tostring) + "&format=" + (.params.format // "png")'
      response:
        raw: true

  # Generate a logo URL for cryptocurrency
  crypto_url:
    description: Generate CDN URL for a cryptocurrency logo
    params:
      symbol: { type: string, required: true, description: "Crypto symbol (e.g., BTC, ETH)" }
      size: { type: integer, default: 128, description: "Size in pixels" }
      format: { type: string, default: "png", description: "Image format" }
    returns: void
    rest:
      method: GET
      url: '"https://img.logo.dev/crypto:" + .params.symbol + "?token=" + .auth.key + "&size=" + ((.params.size // 128) | tostring) + "&format=" + (.params.format // "png")'
      response:
        raw: true
---

# Logo.dev

Company logo API - get logos for any brand by domain, stock ticker, or company name.

## Setup

1. Sign up at https://www.logo.dev/signup (free tier available)
2. Get your publishable key from https://www.logo.dev/dashboard
3. Add credential in AgentOS Settings → Providers → Logo.dev

## How It Works

Logo.dev is a **CDN** — URLs return images directly, not JSON. The utilities verify the logo exists and return the URL in the response headers.

**URL pattern:**
```
https://img.logo.dev/{identifier}?token=KEY&size=128&format=png
```

## Usage

### Get logo by domain

```bash
curl -X POST http://localhost:3456/api/adapters/logo-dev/logo_url \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "shopify.com", "size": 64}'
```

Returns the verified URL that can be used in `<img>` tags.

### Get logo by ticker

```bash
curl -X POST http://localhost:3456/api/adapters/logo-dev/ticker_url \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"ticker": "AAPL"}'
```

### Get logo by company name

```bash
curl -X POST http://localhost:3456/api/adapters/logo-dev/name_url \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"name": "Shopify"}'
```

### Get crypto logo

```bash
curl -X POST http://localhost:3456/api/adapters/logo-dev/crypto_url \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"symbol": "BTC"}'
```

## Use Cases

- **Adapter icons**: Generate proper logos for adapters that don't have them
- **Contact enrichment**: Add company logos to contacts
- **Entity display**: Show logos in task/project views

## Lookup Methods

| Method | Identifier | Example |
|--------|------------|---------|
| Domain | `shopify.com` | Most reliable |
| Ticker | `ticker:AAPL` | Stock symbols |
| Crypto | `crypto:BTC` | Cryptocurrency |
| Name | `name:Shopify` | Fuzzy matching |
| ISIN | `isin:US0378331005` | International securities |

## Parameters

| Param | Values | Default |
|-------|--------|---------|
| size | 16-800 | 128 |
| format | jpg, png, webp | png |
| theme | auto, light, dark | auto |
| retina | true/false | false |
| fallback | monogram, 404 | monogram |

## Pricing

- **Free**: 1,000 requests/month
- **Pro**: Higher limits
- **Enterprise**: SVG format, custom fallbacks
