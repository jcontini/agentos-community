---
id: firecrawl
name: Firecrawl
description: Web scraping and content extraction for JS-heavy sites
category: search
icon: https://www.google.com/s2/favicons?domain=firecrawl.dev&sz=64
color: "#FF6B35"
protocol: rest

provides:
  - url-extract

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  help_url: https://www.firecrawl.dev/app/api-keys

actions:
  scrape:
    description: Scrape a webpage and return clean markdown content
    params:
      url:
        type: string
        required: true
        description: URL to scrape
      only_main_content:
        type: boolean
        default: "true"
        description: Skip headers, footers, and navigation
    api:
      method: POST
      url: https://api.firecrawl.dev/v1/scrape
      body:
        url: "$PARAM_URL"
        formats: ["markdown"]
        onlyMainContent: "$PARAM_ONLY_MAIN_CONTENT"
      response:
        extract: ".data.markdown"

  scrape_full:
    description: Scrape a webpage with full response (includes metadata, HTML)
    params:
      url:
        type: string
        required: true
        description: URL to scrape
      formats:
        type: string
        default: "markdown"
        description: "Formats: markdown, html, links, screenshot"
    api:
      method: POST
      url: https://api.firecrawl.dev/v1/scrape
      body:
        url: "$PARAM_URL"
        formats: ["$PARAM_FORMATS"]

  search:
    description: Search the web and return results with content
    params:
      query:
        type: string
        required: true
        description: Search query
      limit:
        type: integer
        default: "5"
        description: Number of results (1-10)
    api:
      method: POST
      url: https://api.firecrawl.dev/v1/search
      body:
        query: "$PARAM_QUERY"
        limit: "$PARAM_LIMIT"

  crawl:
    description: Crawl multiple pages from a starting URL
    params:
      url:
        type: string
        required: true
        description: Starting URL to crawl from
      limit:
        type: integer
        default: "10"
        description: Maximum pages to crawl
    api:
      method: POST
      url: https://api.firecrawl.dev/v1/crawl
      body:
        url: "$PARAM_URL"
        limit: "$PARAM_LIMIT"
        formats: ["markdown"]
---

# Firecrawl

Web scraping and content extraction that handles JavaScript-heavy sites. Perfect for scraping SPAs, dynamic content, and sites that block simple requests.

## When to Use

- **JS-heavy sites**: React, Vue, Angular, SPAs
- **Dynamic content**: Content loaded via JavaScript
- **Fallback**: When simpler methods fail or return truncated content
- **Search**: When you need to search and get content in one call

**Cost**: ~$0.009/page for scraping, ~$0.01/search

## Tools

### scrape
Get clean markdown from any webpage. Handles JavaScript rendering automatically.

**Parameters:**
- `url` (required): The URL to scrape
- `only_main_content` (optional): Skip headers/footers, default `true`

**Example:**
```
use-plugin(plugin: "firecrawl", tool: "scrape", params: {url: "https://example.com"})
```

**Returns:** Clean markdown content from the page

### scrape_full
Get full scrape response with metadata, multiple formats, and more detail.

**Parameters:**
- `url` (required): The URL to scrape
- `formats` (optional): Comma-separated list - `markdown`, `html`, `links`, `screenshot`

**Example:**
```
use-plugin(plugin: "firecrawl", tool: "scrape_full", params: {url: "https://example.com", formats: "markdown,links"})
```

**Returns:** Full JSON response with requested formats

### search
Search the web and get content from results in one call.

**Parameters:**
- `query` (required): Search query
- `limit` (optional): Number of results, default 5 (max 10)

**Example:**
```
use-plugin(plugin: "firecrawl", tool: "search", params: {query: "MCP protocol specification"})
```

**Returns:** Search results with page content

### crawl
Crawl multiple pages starting from a URL. Good for documentation sites.

**Parameters:**
- `url` (required): Starting URL
- `limit` (optional): Max pages to crawl, default 10

**Example:**
```
use-plugin(plugin: "firecrawl", tool: "crawl", params: {url: "https://docs.example.com", limit: 20})
```

**Returns:** Array of crawled pages with markdown content

## Tips

- **Use `scrape` for single pages** - fastest and cheapest
- **Use `search` when you don't know the URL** - combines search + scrape
- **Use `crawl` for documentation** - great for getting entire doc sites
- **Check for errors** - API returns descriptive error messages

## Error Handling

Common errors:
- `401 Unauthorized` - Check your API key
- `402 Payment Required` - Credits exhausted, add more
- `429 Too Many Requests` - Rate limited, wait and retry
- Timeout errors - Very large or slow pages
