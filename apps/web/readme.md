---
id: web
name: Web
description: Search the web and extract content from URLs
icon: icon.svg
color: "#8B5CF6"

schema:
  result:
    id:
      type: string
      required: true
      description: Unique result identifier
    url:
      type: string
      required: true
      description: Page URL
    title:
      type: string
      required: true
      description: Page title
    snippet:
      type: string
      description: Text excerpt/summary
    content:
      type: string
      description: Full page content (markdown)
    published_at:
      type: datetime
      description: Publication date (if available)
    score:
      type: number
      description: Relevance score

actions:
  search:
    description: Search the web and return URLs with titles
    readonly: true
    params:
      query:
        type: string
        required: true
        description: Search query (natural language)
      limit:
        type: number
        default: 5
        description: Number of results (1-20)
    returns: result[]

  read:
    description: Extract content from a URL
    readonly: true
    params:
      url:
        type: string
        required: true
        description: URL to extract content from
    returns: result

  whois:
    description: Get full WHOIS registration data for a domain
    readonly: true
    params:
      domain:
        type: string
        required: true
        description: Domain name to lookup (e.g. example.com)

  check:
    description: Quick check if a domain is available for registration
    readonly: true
    params:
      domain:
        type: string
        required: true
        description: Domain name to check (e.g. example.com)

instructions: |
  When searching the web:
  - Use connector: "exa" for fast semantic search (default)
  - Use connector: "firecrawl" for JS-heavy sites (React, Vue, SPAs, Notion)
  
  For domain lookups:
  - Use connector: "whois" for WHOIS lookups and availability checks
  - Domain names should not include protocol (no https://)
  - Include the TLD (e.g. "example.com" not "example")
  
  Workflow:
  1. Search first to find relevant URLs
  2. Read specific URLs to get full content
  
  Performance:
  - Exa is faster and cheaper, use as default
  - Firecrawl renders JavaScript, better for modern web apps
---

# Web

Search the web and extract content from URLs.

## Actions

### search

Search the web for relevant URLs.

```
Web(action: "search", params: {query: "AI agents 2025"})
Web(action: "search", params: {query: "rust async patterns", limit: 10})
```

### read

Extract full content from a URL.

```
Web(action: "read", params: {url: "https://example.com/article"})
```

For JS-heavy sites (React, Vue, Notion), use firecrawl:

```
Web(action: "read", connector: "firecrawl", params: {url: "https://notion.so/page"})
```

### whois

Get full WHOIS registration data for a domain.

```
Web(action: "whois", connector: "whois", params: {domain: "example.com"})
Web(action: "whois", connector: "whois", params: {domain: "google.com"})
```

Returns registrar, registration dates, nameservers, and status.

### check

Quick availability check for a domain.

```
Web(action: "check", connector: "whois", params: {domain: "mycoolstartup.com"})
Web(action: "check", connector: "whois", params: {domain: "example.ai"})
```

Returns availability info - AI interprets the raw WHOIS output.

## Connectors

| Connector | Best For | Features |
|-----------|----------|----------|
| `exa` | Fast semantic search | Neural search, content extraction |
| `firecrawl` | JS-heavy sites | Browser rendering, SPA support |
| `whois` | Domain lookups | WHOIS data, availability checks |

## Tips

- Exa uses neural/semantic search - great for concepts and research
- Firecrawl renders JavaScript - use for React, Vue, Angular, Notion
- WHOIS data may be redacted for privacy-protected domains
- Default to exa for web search, use whois for domain lookups
