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
  header: { x-api-key: .auth.key }
  label: API Key
  help_url: https://dashboard.exa.ai/api-keys
# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  # Search results — index records, not full webpages
  result:
    # --- Standard Display Fields ---
    id: .url
    name: .title
    text: '.text // .summary // (if .highlights then .highlights[0] else null end)'
    url: .url
    image: '.image // .favicon'
    author: .author
    datePublished: .publishedDate

  # Full webpage content (for read operations)
  webpage:
    # --- Standard Display Fields ---
    id: .url
    name: .title
    text: .text
    url: .url
    image: '.image // .favicon'
    author: .author
    datePublished: .publishedDate

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  search:
    description: Search the web using neural/semantic search
    returns: result[]
    wraps_as: search
    web_url: '"https://exa.ai/search?q=" + (.params.query | @uri)'
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, description: "Number of results" }
      category: { type: string, description: "Category of search (e.g. company, research paper, news, tweet, github)" }
      include_text: { type: boolean, description: "Include full text of the results (default: true)" }
    rest:
      method: POST
      url: https://api.exa.ai/search
      body:
        query: .params.query
        numResults: .params.limit
        type: '"auto"'
        category: .params.category
        contents:
          text: 'if .params.include_text != null then .params.include_text else true end'
          summary: true
      response:
        root: "/results"

  read_webpage:
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
        # Uses adapters.webpage (default) — has .text for content
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

### search

Create a web search. Returns search results (index records, not full page content).

```
use({ skill: "exa", tool: "search", params: { query: "rust programming" } })
```

Results are `result` entities — snapshots of what the search engine knew about each URL.
To get full page content, follow up with `read_webpage` on a result's URL.

### read_webpage

Extract full content from a URL.

```
use({ skill: "exa", tool: "read_webpage", params: { url: "https://example.com" } })
```

## Known Limitations

**`read_webpage`**: May fail for URLs that Exa can't crawl (e.g., pages behind auth, rate-limited sites). The API returns empty results with error info in `statuses`. Use `firecrawl` as fallback for problematic URLs.
