---
id: curl
name: Curl
description: Simple URL fetching using curl (no API key needed)
icon: icon.svg
color: "#333333"
tags: [web, fetch, local]
display: browser

instructions: |
  Curl is a simple fallback for fetching URLs.
  - No API key required
  - Works for basic HTML pages
  - No JavaScript rendering (use Firecrawl for SPAs)
  - Good for simple pages, APIs, RSS feeds

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  webpage:
    terminology: Page
    mapping:
      url: .url
      title: .title
      content: .content

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.fetch:
    description: Fetch a URL using curl (simple, no JS rendering)
    returns: webpage
    params:
      url: { type: string, required: true, description: "URL to fetch" }
    command:
      binary: bash
      args:
        - "-c"
        - |
          set -e
          URL="{{params.url}}"
          
          # Fetch the page
          CONTENT=$(curl -sL -A "Mozilla/5.0 (compatible; AgentOS/1.0)" --max-time 30 "$URL")
          
          # Extract title from HTML
          TITLE=$(echo "$CONTENT" | grep -oi '<title[^>]*>[^<]*</title>' | head -1 | sed 's/<[^>]*>//g' || echo "")
          
          # Output JSON
          jq -n \
            --arg url "$URL" \
            --arg title "$TITLE" \
            --arg content "$CONTENT" \
            '{url: $url, title: $title, content: $content}'
      timeout: 35
---

# Curl

Simple URL fetching using curl. No API key required.

## When to Use

- Simple HTML pages
- REST APIs
- RSS/Atom feeds
- When you don't need JavaScript rendering
- As a free fallback when other plugins fail

## Limitations

- No JavaScript rendering (use Firecrawl for React/Vue/Angular)
- Basic content extraction (full HTML, not cleaned)
- May be blocked by some sites

## Examples

```bash
# Fetch a simple page
GET /api/webpages/fetch?url=https://example.com

# Fetch an API
GET /api/webpages/fetch?url=https://api.github.com/users/octocat
```
