---
id: firecrawl
name: Firecrawl
description: Read webpages with browser rendering for JS-heavy sites
color: "#FF5308"
website: "https://firecrawl.dev"
privacy_url: "https://www.firecrawl.dev/privacy"
terms_url: "https://www.firecrawl.dev/terms-and-conditions"

connections:
  api:
    base_url: https://api.firecrawl.dev/v1
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: API Key
    help_url: https://www.firecrawl.dev/app/api-keys

---

# Firecrawl

Read webpages with full browser rendering. Handles JS-heavy sites that other tools struggle with.

Use a `webpage.search` integration for discovery when needed; use this operation when URLs need a real browser render for `webpage.read`.

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
- Sites that fail with crawl-only `webpage.read` providers
- When you need fresh/live content

## Operation

### read_webpage

Read a URL with browser rendering and return a `webpage` entity.

```js
run({
  skill: "firecrawl",
  tool: "read_webpage",
  params: { url: "https://react.dev/", wait_for_js: 1000 }
})
```

Use `wait_for_js` for pages that need time to hydrate. Leave it at `0` for fast/static pages.
