---
id: firecrawl
name: Firecrawl
description: Web scraping with browser rendering for JS-heavy sites
icon: icon.png
color: "#FF6B35"
tags: [web, search, scraping]
display: browser

website: https://firecrawl.dev
privacy_url: https://www.firecrawl.dev/privacy
terms_url: https://www.firecrawl.dev/terms-and-conditions

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: API Key
  help_url: https://www.firecrawl.dev/app/api-keys

instructions: |
  Firecrawl-specific notes:
  - Renders JavaScript - use for React, Vue, Angular, SPAs
  - Good for Notion pages, dynamic content
  - Slower than Exa but handles modern web apps
  - Cost: ~$0.009/page for scrape, ~$0.01/search

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  webpage:
    terminology: Page
    # Note: Firecrawl uses different field names for search vs read
    # Search: .url, .title, .description
    # Read: .metadata.sourceURL, .metadata.title, .markdown
    # So we use inline mappings in operations and leave adapter mapping empty
    mapping: {}

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.search:
    description: Search the web with browser rendering
    returns: webpage[]
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 5, description: "Number of results" }
    rest:
      method: POST
      url: https://api.firecrawl.dev/v1/search
      body:
        query: "{{params.query}}"
        limit: "{{params.limit | default:5}}"
      response:
        root: "/data"
        mapping:
          url: ".url"
          title: ".title"
          snippet: ".description"

  webpage.read:
    description: Scrape a URL with browser rendering (handles JS-heavy sites)
    returns: webpage
    params:
      url: { type: string, required: true, description: "URL to scrape" }
      wait_for_js: { type: integer, default: 0, description: "Milliseconds to wait for JS (0=fast, 1000+=for SPAs)" }
      timeout: { type: integer, default: 30000, description: "Request timeout in ms" }
    rest:
      method: POST
      url: https://api.firecrawl.dev/v1/scrape
      body:
        url: "{{params.url}}"
        formats:
          - markdown
        onlyMainContent: true
        waitFor: "{{params.wait_for_js | default:0}}"
        timeout: "{{params.timeout | default:30000}}"
      response:
        root: "/data"
        mapping:
          url: ".metadata.sourceURL"
          title: ".metadata.title"
          content: ".markdown"
---

# Firecrawl

Web scraping with browser rendering. Handles JS-heavy sites that other tools struggle with.

## Setup

1. Get your API key from https://www.firecrawl.dev/app/api-keys
2. Add credential in AgentOS Settings → Providers → Firecrawl

## Features

- Full browser rendering
- SPA support (React, Vue, Angular)
- Notion page scraping
- Main content extraction

## When to Use

- JS-heavy sites (React, Vue, Angular)
- Notion pages
- Sites that fail with Exa
- When you need fresh/live content
