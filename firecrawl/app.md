---
id: firecrawl
name: Firecrawl
description: Web scraping and search for JS-heavy sites with browser rendering
icon: https://www.firecrawl.dev/favicon.ico
color: "#FF6B35"

website: https://firecrawl.dev
privacy_url: https://www.firecrawl.dev/privacy
terms_url: https://www.firecrawl.dev/terms-and-conditions

tags: [web search, URL extraction, scraping, research]

provides:
  web-search:
    action: search
    params:
      query: "{{query}}"
      num_results: "{{num_results}}"
  url-extract:
    action: scrape
    params:
      urls: "{{url}}"

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  help_url: https://www.firecrawl.dev/app/api-keys

settings:
  num_results:
    label: Number of Results
    description: Default number of search results (1-20)
    type: integer
    default: "5"
    min: 1
    max: 20
  only_main_content:
    label: Main Content Only
    description: Extract only main content, skip headers/footers/nav
    type: boolean
    default: "true"

actions:
  search:
    readonly: true
    description: |
      Web search returning URLs, titles, and snippets.
      Fast - does NOT scrape page content. Use `scrape` to get full content from specific URLs.
    params:
      query:
        type: string
        required: true
        description: Search query
      num_results:
        type: integer
        default: "5"
        description: Number of results (1-20)
      lang:
        type: string
        description: Language code (e.g., "en")
      country:
        type: string
        description: Country code (e.g., "us")
    rest:
      method: POST
      url: https://api.firecrawl.dev/v1/search
      body:
        query: $PARAM_QUERY
        limit: $PARAM_NUM_RESULTS
        lang: $PARAM_LANG
        country: $PARAM_COUNTRY

  scrape:
    readonly: true
    description: |
      Extract content from a URL. Uses browser rendering for JS-heavy sites.
      Good for SPAs (React, Vue, Angular), Notion pages, dynamic content.
    params:
      url:
        type: string
        required: true
        description: URL to scrape
      formats:
        type: string
        default: "markdown"
        description: "Output format: markdown, html, or both (comma-separated)"
      only_main_content:
        type: boolean
        default: "true"
        description: Extract only main content, skip nav/footer
    rest:
      method: POST
      url: https://api.firecrawl.dev/v1/scrape
      body:
        url: $PARAM_URL
        formats:
          - markdown
        onlyMainContent: $PARAM_ONLY_MAIN_CONTENT

  crawl:
    readonly: true
    description: |
      Crawl a website and extract content from multiple pages.
      Useful for documentation sites, blogs, knowledge bases.
    params:
      url:
        type: string
        required: true
        description: Starting URL to crawl
      limit:
        type: integer
        default: "10"
        description: Maximum pages to crawl (1-100)
      only_main_content:
        type: boolean
        default: "true"
        description: Extract only main content per page
    rest:
      method: POST
      url: https://api.firecrawl.dev/v1/crawl
      body:
        url: $PARAM_URL
        limit: $PARAM_LIMIT
        scrapeOptions:
          formats:
            - markdown
          onlyMainContent: $PARAM_ONLY_MAIN_CONTENT
---

# Firecrawl

Web scraping and search with browser rendering. Handles JS-heavy sites that other tools struggle with.

## Security

This plugin uses AgentOS secure REST executor. Credentials are never exposed to scripts.

## When to Use Firecrawl

Use Firecrawl when:
- **JS-heavy sites**: React, Vue, Angular, SPAs, Notion pages
- **Other providers fail**: Exa returns errors or truncated content
- **Fresh content needed**: Firecrawl always fetches live (no caching)
- **Multi-page crawl**: Need content from an entire site/section

**Cost:** ~$0.009/page for scrape, ~$0.01/search

## Recommended Workflow

**Fast (2 steps):**
1. `search` → Get URLs and titles (~1s)
2. `scrape` → Get full content from URLs you need

**Multi-page:**
- `crawl` → Scrape an entire site/section

## Tools

### search ⚡ (fast)

Web search returning URLs, titles, and snippets. Does NOT scrape page content.

```
tool: search
params: {query: "AI agents 2025"}
```

With more results:
```
tool: search
params: {query: "AI agents 2025", num_results: 10}
```

### scrape

Extract full content from a URL. Uses browser rendering for JS-heavy sites.

```
tool: scrape
params: {url: "https://notion.so/some-page"}
```

### crawl

Crawl multiple pages from a site. Good for docs, blogs, knowledge bases.

```
tool: crawl
params: {url: "https://docs.example.com", limit: 20}
```

## Comparison with Exa

| Feature | Exa | Firecrawl |
|---------|-----|-----------|
| Speed | ⚡ Faster | Slower |
| Cost | Cheaper | ~$0.009/page |
| JS rendering | ❌ Limited | ✅ Full browser |
| Semantic search | ✅ Neural | ❌ Keyword-based |
| Multi-page crawl | ❌ No | ✅ Yes |

**Recommendation:** Try Exa first, use Firecrawl as fallback or for JS-heavy sites.
