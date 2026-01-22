---
id: reddit
name: Reddit
description: Read public Reddit communities, posts, and comments
icon: icon.png
color: "#FF4500"
tags: [web, social, reddit, communities]

website: https://reddit.com
privacy_url: https://www.reddit.com/policies/privacy-policy
terms_url: https://www.redditinc.com/policies/user-agreement

instructions: |
  Reddit-specific notes:
  - Uses public JSON endpoints (no auth needed)
  - Rate limited to ~10 requests/minute
  - Works for any public subreddit, post, or user profile
  - Add .json to any Reddit URL to get JSON data

# Action implementations (merged from mapping.yaml)
actions:
  search:
    operation: read
    label: "Search Reddit"
    description: "Search posts across all of Reddit or within a specific subreddit"
    command:
      binary: curl
      args:
        - "-s"
        - "-A"
        - "AgentOS/1.0 (github.com/joehewett/agentos)"
        - "https://www.reddit.com/search.json?q={{params.query}}&limit={{params.limit | default:10}}&sort={{params.sort | default:relevance}}"
      timeout: 30
    response:
      root: "data.children"
      mapping:
        id: "[].data.id"
        title: "[].data.title"
        url: "[].data.url"
        subreddit: "[].data.subreddit"
        author: "[].data.author"
        score: "[].data.score"
        num_comments: "[].data.num_comments"
        created_utc: "[].data.created_utc"
        selftext: "[].data.selftext"
        permalink: "[].data.permalink"
        connector: "'reddit'"

  read:
    operation: read
    label: "Read Reddit URL"
    description: "Get data from any Reddit URL (subreddit, post, user profile)"
    command:
      binary: curl
      args:
        - "-s"
        - "-A"
        - "AgentOS/1.0 (github.com/joehewett/agentos)"
        - "{{params.url}}.json"
      timeout: 30
    response:
      mapping:
        url: "{{params.url}}"
        connector: "'reddit'"

  subreddit:
    operation: read
    label: "Get subreddit posts"
    description: "Get recent posts from a subreddit"
    command:
      binary: curl
      args:
        - "-s"
        - "-A"
        - "AgentOS/1.0 (github.com/joehewett/agentos)"
        - "https://www.reddit.com/r/{{params.subreddit}}/{{params.sort | default:hot}}.json?limit={{params.limit | default:25}}"
      timeout: 30
    response:
      root: "data.children"
      mapping:
        id: "[].data.id"
        title: "[].data.title"
        url: "[].data.url"
        author: "[].data.author"
        score: "[].data.score"
        num_comments: "[].data.num_comments"
        created_utc: "[].data.created_utc"
        selftext: "[].data.selftext"
        permalink: "[].data.permalink"
        is_self: "[].data.is_self"
        thumbnail: "[].data.thumbnail"
        connector: "'reddit'"

  post:
    operation: read
    label: "Get post with comments"
    description: "Get a Reddit post and its comments by post ID"
    command:
      binary: curl
      args:
        - "-s"
        - "-A"
        - "AgentOS/1.0 (github.com/joehewett/agentos)"
        - "https://www.reddit.com/comments/{{params.post_id}}.json?limit={{params.comment_limit | default:100}}"
      timeout: 30
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
