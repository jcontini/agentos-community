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

## Usage

### search

Create a web search. Returns search results (index records, not full page content).

```
run({ skill: "exa", tool: "search", params: { query: "rust programming" } })
```

Results are `result` entities — snapshots of what the search engine knew about each URL.
To get full page content, follow up with `read_webpage` on a result's URL.

### read_webpage

Extract full content from a URL.

```
run({ skill: "exa", tool: "read_webpage", params: { url: "https://example.com" } })
```

## Known Limitations

**`read_webpage`**: May fail for URLs the crawl API cannot fetch (e.g., pages behind auth, rate-limited sites). The API returns empty results with error info in `statuses`. Retry with another integration that implements `webpage.read` using a real browser if you need JS rendering.
