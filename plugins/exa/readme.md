---
id: exa
name: Exa
description: Semantic web search and content extraction
icon: icon.png
color: "#5436DA"
tags: [web, search, scraping]
display: browser

website: https://exa.ai
privacy_url: https://exa.ai/privacy
terms_url: https://exa.ai/terms

auth:
  type: api_key
  header: x-api-key
  label: API Key
  help_url: https://dashboard.exa.ai/api-keys

# Terminology: how this service names entities
terminology:
  webpage: Result

instructions: |
  Exa-specific notes:
  - Neural search finds content by meaning, not just keywords
  - Fast: typically under 1 second per request
  - Use for research, concepts, "how to" queries

# Entity implementations
# Structure: entities.{entity}.{operation} = executor
entities:
  webpage:
    search:
      label: "Search web"
      rest:
        method: POST
        url: https://api.exa.ai/search
        body:
          query: "{{params.query}}"
          numResults: "{{params.limit | default:5}}"
          type: "auto"
        response:
          root: "results"
          mapping:
            url: ".url"
            title: ".title"
            snippet: ".text"
            published_at: ".publishedDate"

    read:
      label: "Read URL"
      rest:
        method: POST
        url: https://api.exa.ai/contents
        body:
          urls:
            - "{{params.url}}"
          text: true
        response:
          root: "results[0]"
          mapping:
            url: ".url"
            title: ".title"
            content: ".text"
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

**`read` action**: May fail for URLs that Exa can't crawl (e.g., `example.com`, pages behind auth, rate-limited sites). The API returns empty results with error info in `statuses`, but the current plugin doesn't surface this gracefully. Use `firecrawl.read` as fallback for problematic URLs.

The Exa API returns:
```json
{ "results": [], "statuses": [{ "id": "url", "status": "error", "error": { "tag": "CRAWL_NOT_FOUND" } }] }
```

TODO: Enhance executor to handle empty array access and surface `statuses` errors.
