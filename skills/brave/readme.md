---
id: brave
name: Brave Search
description: Privacy-focused web search with independent index
color: "#F83B1D"
website: "https://brave.com/search"
privacy_url: "https://search.brave.com/help/privacy-policy"
terms_url: "https://brave.com/terms-of-use"

connections:
  api:
    base_url: https://api.search.brave.com/res/v1
    auth:
      type: api_key
      header:
        X-Subscription-Token: .auth.key
    label: API Key
    help_url: https://api-dashboard.search.brave.com/app/keys

operations:
  search:
    wraps_as: search
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

## Usage

### search

Create a web search. Returns search results (index records).

```
run({ skill: "brave", tool: "search", params: { query: "rust programming" } })
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
