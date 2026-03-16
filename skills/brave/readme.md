---
id: brave
name: Brave Search
description: Privacy-focused web search with independent index
icon: icon.svg
color: "#F83B1D"

website: https://brave.com/search
privacy_url: https://search.brave.com/help/privacy-policy
terms_url: https://brave.com/terms-of-use

auth:
  header: { X-Subscription-Token: .auth.key }
  label: API Key
  help_url: https://api-dashboard.search.brave.com/app/keys

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  result:
    id: .url
    url: .url
    title: .title
    snippet: .description
    favicon: .meta_url.favicon
    indexed_at: .page_age

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  search:
    description: Search the web using Brave's independent index
    returns: result[]
    wraps_as: search
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, description: "Number of results (max 20)" }
      freshness: { type: string, description: "Filter by date: pd (24h), pw (week), pm (month), py (year)" }
    rest:
      method: GET
      url: https://api.search.brave.com/res/v1/web/search
      query:
        q: ".params.query"
        count: ".params.limit // 20"
        freshness: ".params.freshness"
      response:
        root: "/web/results"
---

# Brave Search

Privacy-focused web search powered by Brave's independent index.

## Setup

1. Sign up at https://api-dashboard.search.brave.com
2. Get your API key from the dashboard
3. Add credential in AgentOS Settings

## Features

- **Independent index** - Not a Google/Bing wrapper
- **Privacy-focused** - No tracking
- **Free tier** - 2,000 queries/month
- **Search operators** - Quotes, exclusions, site: filters

## Operations

### search

Create a web search. Returns search results (index records).

```
use({ skill: "brave", tool: "search", params: { query: "rust programming" } })
```

### Search Operators

Include these in your query:
- `"exact phrase"` - Match exact phrase
- `-exclude` - Exclude term
- `site:github.com` - Limit to domain
- `filetype:pdf` - Filter by file type

### Freshness Filters

- `pd` - Past day (24 hours)
- `pw` - Past week
- `pm` - Past month
- `py` - Past year
