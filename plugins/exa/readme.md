---
id: exa
name: Exa
description: Semantic web search and content extraction
icon: icon.png
tags: [web, search]
display: browser

website: https://exa.ai
privacy_url: https://exa.ai/privacy
terms_url: https://exa.ai/terms

auth:
  type: api_key
  header: x-api-key
  label: API Key
  help_url: https://dashboard.exa.ai/api-keys

instructions: |
  Exa-specific notes:
  - Neural search finds content by meaning, not just keywords
  - Fast: typically under 1 second per request
  - Use for research, concepts, "how to" queries

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  webpage:
    terminology: Result
    # Default mapping for fetch operations (has full content)
    mapping:
      url: .url
      title: .title
      content: .text
      favicon: .favicon
      published_at: .publishedDate

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.search:
    description: Search the web using neural/semantic search
    returns: webpage[]
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 5, description: "Number of results" }
    rest:
      method: POST
      url: https://api.exa.ai/search
      body:
        query: "{{params.query}}"
        numResults: "{{params.limit | default:5}}"
        type: "auto"
      response:
        root: "/results"
        # Search results have different shape than read (no .text field)
        mapping:
          url: .url
          title: .title
          published_at: .publishedDate

  webpage.read:
    description: Extract content from a URL
    returns: webpage
    params:
      url: { type: string, required: true, description: "URL to fetch" }
    rest:
      method: POST
      url: https://api.exa.ai/contents
      body:
        urls:
          - "{{params.url}}"
        text: true
      response:
        root: "/results/0"
        # Uses adapter.mapping (default) — has .text for content
---

# Exa

Semantic web search and content extraction. Neural search finds content by meaning, not just keywords.

## Setup

1. Get your API key from https://dashboard.exa.ai/api-keys
2. Add credential in AgentOS Settings → Providers → Exa

## Features

- Neural/semantic search
- Fast content extraction
- Find similar pages
- Relevance scoring

## When to Use

- Research and concepts
- "How to" queries
- Finding related content
- Fast searches (default provider)

## Known Limitations

**`fetch` action**: May fail for URLs that Exa can't crawl (e.g., `example.com`, pages behind auth, rate-limited sites). The API returns empty results with error info in `statuses`, but the current plugin doesn't surface this gracefully. Use `firecrawl.fetch` as fallback for problematic URLs.

The Exa API returns:
```json
{ "results": [], "statuses": [{ "id": "url", "status": "error", "error": { "tag": "CRAWL_NOT_FOUND" } }] }
```

TODO: Enhance executor to handle empty array access and surface `statuses` errors.
