---
id: reddit
name: Reddit
description: Read public Reddit communities, posts, and comments
icon: icon.svg
color: "#FF4500"

website: https://reddit.com
privacy_url: https://www.reddit.com/policies/privacy-policy
terms_url: https://www.redditinc.com/policies/user-agreement

instructions: |
  Reddit-specific notes:
  - Uses public JSON endpoints (no auth needed)
  - Rate limited to ~10 requests/minute
  - Works for any public subreddit, post, or user profile
  - Add .json to any Reddit URL to get JSON data
---

# Reddit

Access public Reddit data using Reddit's built-in JSON endpoints.

## How it works

Reddit exposes a public JSON API by simply appending `.json` to any URL:
- `reddit.com/r/programming.json` → subreddit posts
- `reddit.com/r/programming/new.json` → new posts
- `reddit.com/comments/{id}.json` → post with comments
- `reddit.com/search.json?q=query` → search results

No authentication required, just a custom User-Agent header to avoid rate limiting.

## No Setup Required

Unlike the official Reddit API (which now requires pre-approval), this connector uses Reddit's public JSON endpoints that work immediately without any configuration.

## Rate Limits

- ~10 requests per minute without OAuth
- Sufficient for browsing and casual use

## Actions

| Action | Description |
|--------|-------------|
| `search` | Search posts across Reddit |
| `read` | Read any Reddit URL as JSON |
| `subreddit` | Get posts from a subreddit |
| `post` | Get a post with its comments |

## Examples

```yaml
# Get hot posts from r/programming
Web(action: "subreddit", connector: "reddit", params: {subreddit: "programming"})

# Search for posts about TypeScript
Web(action: "search", connector: "reddit", params: {query: "typescript tips"})

# Get new posts sorted by new
Web(action: "subreddit", connector: "reddit", params: {subreddit: "webdev", sort: "new"})
```
