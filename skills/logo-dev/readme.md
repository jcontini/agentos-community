---
id: logo-dev
name: Logo.dev
description: "Company logos via CDN - lookup by domain, ticker, or name"
color: "#635BFF"
website: "https://www.logo.dev"
privacy_url: "https://www.logo.dev/privacy"
terms_url: "https://www.logo.dev/terms"

connections:
  api:
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: Publishable Key
    help_url: https://www.logo.dev/dashboard
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
