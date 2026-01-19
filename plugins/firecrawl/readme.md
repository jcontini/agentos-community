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

# Terminology: how this service names entities
terminology:
  webpage: Page

instructions: |
  Firecrawl-specific notes:
  - Renders JavaScript - use for React, Vue, Angular, SPAs
  - Good for Notion pages, dynamic content
  - Slower than Exa but handles modern web apps
  - Cost: ~$0.009/page for scrape, ~$0.01/search

# Entity implementations
# Structure: entities.{entity}.{operation} = executor
entities:
  webpage:
    search:
      label: "Search web"
      rest:
        method: POST
        url: https://api.firecrawl.dev/v1/search
        body:
          query: "{{params.query}}"
          limit: "{{params.limit | default:5}}"
        response:
          root: "data"
          mapping:
            url: ".url"
            title: ".title"
            snippet: ".description"

    read:
      label: "Read URL"
      rest:
        method: POST
        url: https://api.firecrawl.dev/v1/scrape
        body:
          url: "{{params.url}}"
          formats:
            - markdown
          onlyMainContent: true
        response:
          root: "data"
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
