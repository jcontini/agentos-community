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

```js
use({ skill: "curl", tool: "read_webpage", params: { url: "https://example.com" } })

use({ skill: "curl", tool: "read_webpage", params: { url: "https://api.github.com/users/octocat" } })
```
