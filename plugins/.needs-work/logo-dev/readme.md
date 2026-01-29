---
id: logo-dev
name: Logo.dev
description: Company logos via CDN - lookup by domain, ticker, or name
icon: icon.svg
tags: [media, brands]
display: gallery

website: https://www.logo.dev
privacy_url: https://www.logo.dev/privacy
terms_url: https://www.logo.dev/terms

auth:
  type: api_key
  query_param: token
  label: Publishable Key
  help_url: https://www.logo.dev/dashboard

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
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  image:
    terminology: Logo
    mapping:
      url: .url
      domain: .domain
      format: .format
      size: .size
  
  file:
    terminology: Downloaded Logo
    mapping:
      path: .path
      name: .name
      mime_type: .mime_type
      size: .size
      source_url: .source_url

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS (requires download executor - see todo/downloads.md)
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  # Download logo to local file
  # NOTE: Requires 'download' executor which is planned but not yet implemented
  file.download:
    description: Download logo to ~/.agentos/downloads/
    returns: file
    params:
      domain: { type: string, required: true, description: "Domain (e.g., shopify.com)" }
      size: { type: integer, default: 128, description: "Size in pixels (16-800)" }
      format: { type: string, default: "png", description: "Image format (jpg, png, webp)" }
    download:
      url: "https://img.logo.dev/{{params.domain}}?token={{credential}}&size={{params.size | default:128}}&format={{params.format | default:'png'}}"
      destination: "images/logo-dev/{{params.domain}}.{{params.format | default:'png'}}"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  # Generate a logo URL for a domain
  logo_url:
    description: Generate CDN URL for a company logo
    params:
      domain: { type: string, required: true, description: "Domain (e.g., shopify.com)" }
      size: { type: integer, default: 128, description: "Size in pixels (16-800)" }
      format: { type: string, default: "png", description: "Image format (jpg, png, webp)" }
      theme: { type: string, default: "auto", description: "Theme (auto, light, dark)" }
      retina: { type: boolean, default: false, description: "Double resolution for retina" }
    template:
      url: "https://img.logo.dev/{{params.domain}}?token={{credential}}&size={{params.size | default:128}}&format={{params.format | default:'png'}}&theme={{params.theme | default:'auto'}}{{#if params.retina}}&retina=true{{/if}}"

  # Generate a logo URL for a stock ticker
  ticker_logo_url:
    description: Generate CDN URL for a company logo by stock ticker
    params:
      ticker: { type: string, required: true, description: "Stock ticker (e.g., AAPL)" }
      size: { type: integer, default: 128, description: "Size in pixels" }
      format: { type: string, default: "png", description: "Image format" }
    template:
      url: "https://img.logo.dev/ticker:{{params.ticker}}?token={{credential}}&size={{params.size | default:128}}&format={{params.format | default:'png'}}"

  # Generate a logo URL by company name
  name_logo_url:
    description: Generate CDN URL for a company logo by name
    params:
      name: { type: string, required: true, description: "Company name (e.g., Shopify)" }
      size: { type: integer, default: 128, description: "Size in pixels" }
      format: { type: string, default: "png", description: "Image format" }
    template:
      url: "https://img.logo.dev/name:{{params.name | urlencode}}?token={{credential}}&size={{params.size | default:128}}&format={{params.format | default:'png'}}"
---

# Logo.dev

Company logo API - get logos for any brand by domain, stock ticker, or company name.

## Setup

1. Sign up at https://www.logo.dev/signup (free tier available)
2. Get your publishable key from https://www.logo.dev/dashboard
3. Add credential in AgentOS Settings → Providers → Logo.dev

## Features

- **Domain lookup**: `shopify.com` → Shopify logo
- **Ticker lookup**: `AAPL` → Apple logo
- **Name lookup**: `Shopify` → Shopify logo
- **Crypto**: `BTC`, `ETH` → Cryptocurrency logos
- Customizable size, format, theme
- Light/dark mode support
- Retina (2x) resolution

## Usage

### Get URL for display

Logo.dev is a CDN - URLs return images directly. Use the utilities to generate URLs:

```
logo_url(domain: "shopify.com", size: 64, format: "png")
→ https://img.logo.dev/shopify.com?token=KEY&size=64&format=png
```

These URLs can be used directly in `<img>` tags.

### Download to local file

*(Requires download executor - coming soon)*

```
file.download(domain: "shopify.com", format: "png")
→ Saves to ~/.agentos/downloads/images/logo-dev/shopify.png
→ Returns file entity { path, name, size, mime_type }
```

Use this to save logos locally for offline access or to populate plugin icons.

## Pricing

- **Free**: 1,000 requests/month, rate limited
- **Pro**: Higher limits, priority support
- **Enterprise**: SVG format, custom fallbacks

## Known Limitations

- SVG format requires Enterprise plan
- Some logos may return monogram fallbacks
- Rate limited on free tier (use API key for production)
