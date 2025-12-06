---
id: exa
name: Exa
description: Semantic web search
category: search

icon: https://www.google.com/s2/favicons?domain=exa.ai&sz=64
color: "#5046E5"

abilities:
  - id: search
    label: "Search the web"
    endpoints:
      - "POST /search"
      - "POST /findSimilar"
  - id: extract
    label: "Extract content from URLs"
    endpoints:
      - "POST /contents"

auth:
  type: api_key
  header: x-api-key
  prefix: ""
  help_url: https://dashboard.exa.ai/api-keys

api:
  base_url: https://api.exa.ai
---

# Exa

**Use for:** Semantic web search, content extraction, research

## Quick Start

All requests go through the Passport proxy. Auth is automatic.

```bash
# Search the web
curl -s http://localhost:1111/cloud/exa/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "best practices for React performance",
    "numResults": 5,
    "type": "auto",
    "contents": { "text": true }
  }' | jq '.results[] | {title, url}'

# Extract content from URLs
curl -s http://localhost:1111/cloud/exa/contents \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/article"],
    "text": true,
    "livecrawl": "always"
  }' | jq .
```

## API Reference

**Base URL:** `http://localhost:1111/cloud/exa`

### Search

**POST /search** - Semantic web search

```json
{
  "query": "your search query",
  "numResults": 10,
  "type": "auto",
  "contents": {
    "text": true,
    "livecrawl": "always"
  }
}
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `query` | Natural language search query | required |
| `numResults` | Number of results (1-100) | 10 |
| `type` | `auto`, `neural`, `keyword` | `auto` |
| `contents` | Include page content | omit for URLs only |
| `contents.livecrawl` | Freshness: `always`, `preferred`, `fallback`, `never` | `never` |
| `includeDomains` | Limit to specific domains | none |
| `excludeDomains` | Exclude specific domains | none |

**Search types:**
- `auto` - Let Exa choose (recommended)
- `neural` - Semantic/meaning-based (best for niche content)
- `keyword` - Traditional keyword matching

### Extract

**POST /contents** - Extract content from URLs

```json
{
  "urls": ["https://example.com", "https://another.com"],
  "text": true,
  "livecrawl": "always"
}
```

| Parameter | Description |
|-----------|-------------|
| `urls` | Array of URLs to extract |
| `text` | Return text content (boolean) |
| `livecrawl` | `always` (recommended), `fallback`, `never` |

## Tips

- **Always use `livecrawl: "always"`** for fresh content
- **Exa excels at semantic search** - natural language queries work great
- **For JS-heavy sites** (Notion, React apps), content may be limited

## Links

- [Exa API Docs](https://docs.exa.ai)
