---
id: exa
name: Exa
description: Semantic web search and content extraction for research
category: search
icon: https://www.finsmes.com/wp-content/uploads/2024/07/exa.jpeg
color: "#5436DA"

triggers:
  - needs web search or to extract content from URLs

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

requires:
  - curl  # Usually pre-installed
  - jq    # Usually pre-installed on macOS

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
    description: Search the web with optional content extraction. Use include_text=true only when you need page content.
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
      include_domains:
        type: string
        description: Comma-separated domains to limit search to
      exclude_domains:
        type: string
        description: Comma-separated domains to exclude
    run: |
      # Build JSON payload
      INCLUDE_TEXT="${PARAM_INCLUDE_TEXT:-false}"
      PAYLOAD=$(jq -n \
        --arg query "$PARAM_QUERY" \
        --argjson num "${PARAM_NUM_RESULTS:-5}" \
        --arg type "${PARAM_TYPE:-auto}" \
        --arg text "$INCLUDE_TEXT" \
        --arg livecrawl "${PARAM_LIVECRAWL:-never}" \
        --arg include "$PARAM_INCLUDE_DOMAINS" \
        --arg exclude "$PARAM_EXCLUDE_DOMAINS" \
        '{
          query: $query,
          numResults: $num,
          type: $type
        }
        + (if $text == "true" then {contents: {text: true, livecrawl: $livecrawl}} else {} end)
        + (if $include != "" then {includeDomains: ($include | split(",") | map(gsub("^\\s+|\\s+$"; "")))} else {} end)
        + (if $exclude != "" then {excludeDomains: ($exclude | split(",") | map(gsub("^\\s+|\\s+$"; "")))} else {} end)')
      
      curl -s -m 30 -X POST "https://api.exa.ai/search" \
        -H "x-api-key: $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" | jq .

  search_urls:
    readonly: true
    description: Quick search returning just URLs and titles (fastest, cheapest)
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
    run: |
      curl -s -m 15 -X POST "https://api.exa.ai/search" \
        -H "x-api-key: $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
          \"query\": \"$PARAM_QUERY\",
          \"numResults\": ${PARAM_NUM_RESULTS:-5},
          \"type\": \"${PARAM_TYPE:-auto}\"
        }" | jq -r '.results[] | "\(.title)\n  \(.url)\n"'

  extract:
    readonly: true
    description: Extract content from specific URLs (use after search_urls to get full content)
    params:
      urls:
        type: string
        required: true
        description: Comma-separated URLs to extract content from
      livecrawl:
        type: string
        default: "never"
        description: "Freshness: never (fastest), fallback, always (slowest)"
    run: |
      # Convert comma-separated URLs to JSON array
      URLS_JSON=$(echo "$PARAM_URLS" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; ""))')
      
      curl -s -m 45 -X POST "https://api.exa.ai/contents" \
        -H "x-api-key: $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
          \"urls\": $URLS_JSON,
          \"text\": true,
          \"livecrawl\": \"${PARAM_LIVECRAWL:-never}\"
        }" | jq .

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
    run: |
      INCLUDE_TEXT="${PARAM_INCLUDE_TEXT:-false}"
      PAYLOAD=$(jq -n \
        --arg url "$PARAM_URL" \
        --argjson num "${PARAM_NUM_RESULTS:-5}" \
        --arg text "$INCLUDE_TEXT" \
        '{
          url: $url,
          numResults: $num
        }
        + (if $text == "true" then {contents: {text: true, livecrawl: "never"}} else {} end)')
      
      curl -s -m 30 -X POST "https://api.exa.ai/findSimilar" \
        -H "x-api-key: $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" | jq .
---

# Exa

Semantic web search and content extraction. Neural search finds content by meaning, not just keywords.

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
Get content from specific URLs.

```
tool: extract
params: {urls: "https://docs.exa.ai/reference/search"}
```

Multiple URLs:
```
tool: extract
params: {urls: "https://example.com/page1,https://example.com/page2"}
```

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
