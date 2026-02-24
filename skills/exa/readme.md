---
id: exa
name: Exa
description: Semantic web search and content extraction
icon: icon.png
color: "#1F40ED"

website: https://exa.ai
privacy_url: https://exa.ai/privacy
terms_url: https://exa.ai/terms

auth:
  type: api_key
  header: x-api-key
  label: API Key
  help_url: https://dashboard.exa.ai/api-keys

connects_to: exa

seed:
  - id: exa
    types: [software]
    name: Exa
    data:
      software_type: api
      url: https://exa.ai
      launched: "2022"
      platforms: [api]
      pricing: freemium
    relationships:
      - role: offered_by
        to: exa-ai

  - id: exa-ai
    types: [organization]
    name: Exa AI Inc.
    data:
      type: company
      url: https://exa.ai
      founded: "2021"

instructions: |
  Exa-specific notes:
  - Neural search finds content by meaning, not just keywords
  - Fast: typically under 1 second per request
  - Use for research, concepts, "how to" queries

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  # Search results — index records, not full webpages
  result:
    terminology: Result
    mapping:
      id: .url
      url: .url
      title: .title
      snippet: .text
      favicon: .favicon
      indexed_at: .publishedDate

  # Full webpage content (for read operations)
  webpage:
    terminology: Page
    mapping:
      url: .url
      title: .title
      favicon: .favicon
      published_at: .publishedDate
      content: .text

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  search.create:
    description: Search the web using neural/semantic search
    returns: result[]
    wraps_as: search
    web_url: '"https://exa.ai/search?q=" + (.params.query | @uri)'
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 5, description: "Number of results" }
    rest:
      method: POST
      url: https://api.exa.ai/search
      body:
        query: .params.query
        numResults: .params.limit
        type: '"auto"'
      response:
        root: "/results"
        mapping:
          id: .url
          url: .url
          title: .title
          indexed_at: .publishedDate

  webpage.read:
    description: Extract full content from a URL
    returns: webpage
    web_url: .params.url
    params:
      url: { type: string, required: true, description: "URL to fetch" }
    rest:
      method: POST
      url: https://api.exa.ai/contents
      body:
        urls:
          - .params.url
        text: true
      response:
        root: "/results/0"
        # Uses transformer.webpage.mapping (default) — has .text for content
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

## Operations

### search.create

Create a web search. Returns search results (index records, not full page content).

```
use({ skill: "exa", tool: "search.create", params: { query: "rust programming" } })
```

Results are `result` entities — snapshots of what the search engine knew about each URL.
To get full page content, follow up with `webpage.read` on a result's URL.

### webpage.read

Extract full content from a URL.

```
use({ skill: "exa", tool: "webpage.read", params: { url: "https://example.com" } })
```

## Known Limitations

**`webpage.read`**: May fail for URLs that Exa can't crawl (e.g., pages behind auth, rate-limited sites). The API returns empty results with error info in `statuses`. Use `firecrawl` as fallback for problematic URLs.
