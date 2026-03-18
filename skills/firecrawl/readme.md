---
id: firecrawl
name: Firecrawl
description: Read webpages with browser rendering for JS-heavy sites
icon: icon.png
color: "#FF5308"

website: https://firecrawl.dev
privacy_url: https://www.firecrawl.dev/privacy
terms_url: https://www.firecrawl.dev/terms-and-conditions

connections:
  api:
    base_url: "https://api.firecrawl.dev/v1"
    header: { Authorization: '"Bearer " + .auth.key' }
    label: API Key
    help_url: https://www.firecrawl.dev/app/api-keys
# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  webpage:
    id: '.metadata.sourceURL // .metadata.url // .url'
    name: '.metadata.title // .metadata.ogTitle // .title'
    text: '.markdown // .metadata.description'
    url: '.metadata.sourceURL // .metadata.url // .url'
    image: '.metadata.ogImage // .metadata.image // .metadata["og:image"]'
    author: '.metadata.author // .metadata["article:author"]'
    datePublished: '.metadata.publishedTime // .metadata.publishedDate // .metadata["article:published_time"]'
    data.content_type: '"text/markdown"'

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  read_webpage:
    description: Read a URL with browser rendering (handles JS-heavy sites)
    returns: webpage
    web_url: .params.url
    params:
      url: { type: string, required: true, description: "URL to read" }
      wait_for_js: { type: integer, default: 0, description: "Milliseconds to wait for JS (0=fast, 1000+=for SPAs)" }
      timeout: { type: integer, default: 30000, description: "Request timeout in ms" }
    rest:
      method: POST
      url: /scrape
      body:
        url: .params.url
        formats:
          - '"markdown"'
        onlyMainContent: true
        waitFor: .params.wait_for_js
        timeout: .params.timeout
      response:
        root: "/data"
---

# Firecrawl

Read webpages with full browser rendering. Handles JS-heavy sites that other tools struggle with.

Use Exa for discovery/search, then use Firecrawl to fetch URLs that need a real browser render.

## Setup

1. Get your API key from https://www.firecrawl.dev/app/api-keys
2. Add credential in AgentOS Settings → Providers → Firecrawl

## Features

- Full browser rendering
- SPA support (React, Vue, Angular)
- Notion page reading
- Main content extraction

## When to Use

- JS-heavy sites (React, Vue, Angular)
- Notion pages
- Sites that fail with Exa
- When you need fresh/live content

## Operation

### read_webpage

Read a URL with browser rendering and return a `webpage` entity.

```js
use({
  skill: "firecrawl",
  tool: "read_webpage",
  params: { url: "https://react.dev/", wait_for_js: 1000 }
})
```

Use `wait_for_js` for pages that need time to hydrate. Leave it at `0` for fast/static pages.
