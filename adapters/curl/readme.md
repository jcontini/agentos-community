---
id: curl
name: Curl
description: Simple URL fetching using curl (no API key needed)
icon: icon.svg
color: "#333333"

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
      content_type: .content_type

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.read:
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
          
          # Create temp file for headers
          HEADERS_FILE=$(mktemp)
          trap "rm -f $HEADERS_FILE" EXIT
          
          # Fetch the page with headers dumped to file
          CONTENT=$(curl -sL -A "Mozilla/5.0 (compatible; AgentOS/1.0)" --max-time 30 -D "$HEADERS_FILE" "$URL")
          
          # Extract Content-Type from headers (e.g., "application/json; charset=utf-8" -> "application/json")
          CONTENT_TYPE=$(grep -i '^content-type:' "$HEADERS_FILE" | tail -1 | cut -d: -f2 | cut -d';' -f1 | tr -d ' \r' || echo "text/plain")
          
          # Extract title from HTML (only for HTML content)
          TITLE=""
          if [[ "$CONTENT_TYPE" == text/html* ]]; then
            TITLE=$(echo "$CONTENT" | grep -oi '<title[^>]*>[^<]*</title>' | head -1 | sed 's/<[^>]*>//g' || echo "")
          fi
          
          # Output JSON
          jq -n \
            --arg url "$URL" \
            --arg title "$TITLE" \
            --arg content "$CONTENT" \
            --arg content_type "$CONTENT_TYPE" \
            '{url: $url, title: $title, content: $content, content_type: $content_type}'
      timeout: 35
---

# Curl

Simple URL fetching using curl. No API key required.

## When to Use

- Simple HTML pages
- REST APIs
- RSS/Atom feeds
- When you don't need JavaScript rendering
- As a free fallback when other adapters fail

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
