---
id: exa
name: Exa
description: Semantic web search and content extraction for research
icon: https://www.finsmes.com/wp-content/uploads/2024/07/exa.jpeg
color: "#5436DA"

website: https://exa.ai
privacy_url: https://exa.ai/privacy
terms_url: https://exa.ai/terms

tags: [web search, URL extraction, research]

provides:
  web-search:
    action: search_urls
    params:
      query: "{{query}}"
      num_results: "{{num_results}}"
  url-extract:
    action: extract
    params:
      urls: "{{url}}"

auth:
  type: api_key
  header: x-api-key
  help_url: https://dashboard.exa.ai/api-keys

# No shell dependencies - all actions use secure REST executor

settings:
  num_results:
    label: Number of Results
    description: Default number of search results to return (1-100)
    type: integer
    default: "5"
    min: 1
    max: 100
  livecrawl:
    label: Live Crawl Preference
    description: Freshness preference for content (never = fastest, always = slowest)
    type: enum
    default: "never"
    options:
      - never
      - fallback
      - preferred
      - always
  include_text:
    label: Include Text Content
    description: Include page text content by default (slower, use only when needed)
    type: boolean
    default: "false"
  type:
    label: Search Type
    description: Default search type (auto = let Exa choose, neural = concepts/research, keyword = exact terms)
    type: enum
    default: "auto"
    options:
      - auto
      - neural
      - keyword

actions:
  search:
    readonly: true
    description: Web search with optional content extraction
    params:
      query:
        type: string
        required: true
        description: Natural language search query
      num_results:
        type: integer
        default: "5"
        description: Number of results (1-100)
      type:
        type: string
        default: "auto"
        description: "Search type: auto, neural, or keyword"
      include_text:
        type: boolean
        default: "false"
        description: Include page text content (slower, use only when needed)
      livecrawl:
        type: string
        default: "never"
        description: "Freshness: never (fastest), fallback, preferred, always (slowest)"
    rest:
      method: POST
      url: https://api.exa.ai/search
      body:
        query: $PARAM_QUERY
        numResults: $PARAM_NUM_RESULTS
        type: $PARAM_TYPE
        contents:
          text: $PARAM_INCLUDE_TEXT
          livecrawl: $PARAM_LIVECRAWL

  search_urls:
    readonly: true
    description: Quick search returning URLs and titles
    params:
      query:
        type: string
        required: true
        description: Natural language search query
      num_results:
        type: integer
        default: "5"
        description: Number of results (1-100)
      type:
        type: string
        default: "auto"
        description: "Search type: auto, neural, or keyword"
    rest:
      method: POST
      url: https://api.exa.ai/search
      body:
        query: $PARAM_QUERY
        numResults: $PARAM_NUM_RESULTS
        type: $PARAM_TYPE

  extract:
    readonly: true
    description: Extract content from a URL
    params:
      url:
        type: string
        required: true
        description: URL to extract content from (call multiple times for multiple URLs)
      livecrawl:
        type: string
        default: "never"
        description: "Freshness: never (fastest), fallback, always (slowest)"
    rest:
      method: POST
      url: https://api.exa.ai/contents
      body:
        urls:
          - $PARAM_URL
        text: true
        livecrawl: $PARAM_LIVECRAWL

  find_similar:
    readonly: true
    description: Find pages similar to a given URL
    params:
      url:
        type: string
        required: true
        description: URL to find similar pages for
      num_results:
        type: integer
        default: "5"
        description: Number of results (1-100)
      include_text:
        type: boolean
        default: "false"
        description: Include page text content (slower)
    rest:
      method: POST
      url: https://api.exa.ai/findSimilar
      body:
        url: $PARAM_URL
        numResults: $PARAM_NUM_RESULTS
        contents:
          text: $PARAM_INCLUDE_TEXT
---

# Exa

Semantic web search and content extraction. Neural search finds content by meaning, not just keywords.

## Security

This plugin uses AgentOS secure REST executor. Credentials are never exposed to scripts - AgentOS injects them directly into API requests.

## Recommended Workflow

**Fast (2 steps):**
1. `search_urls` → Get relevant URLs (~1s)
2. `extract` → Get content from the URLs you need

**Simple (1 step):**
- `search` with `include_text: true` → Slower but gets everything

## Tools

### search_urls ⚡ (fastest)
Quick search returning just URLs and titles.

```
tool: search_urls
params: {query: "macOS default apps"}
```

With more results:
```
tool: search_urls
params: {query: "macOS default apps", num_results: 10}
```

### search
Search with optional content extraction.

```
tool: search
params: {query: "rust async patterns"}
```

With page content (slower):
```
tool: search
params: {query: "rust async patterns", include_text: true, num_results: 3}
```

With fresh/live crawled content (slowest):
```
tool: search
params: {query: "latest AI news", include_text: true, livecrawl: "always"}
```

### extract
Get content from a URL.

```
tool: extract
params: {url: "https://docs.exa.ai/reference/search"}
```

For multiple URLs, call extract multiple times or use `search` with `include_text: true`.

### find_similar
Find pages similar to a URL.

```
tool: find_similar
params: {url: "https://anthropic.com/claude"}
```

## Defaults

| Parameter | Default | Override for |
|-----------|---------|--------------|
| `num_results` | 5 | More results |
| `include_text` | false | Page content |
| `livecrawl` | never | Fresh content (`fallback`, `always`) |

## Search Types

- **auto** (default): Let Exa choose
- **neural**: Concepts, "how to", research
- **keyword**: Names, error messages, exact terms
