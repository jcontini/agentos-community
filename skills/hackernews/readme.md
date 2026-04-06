---
id: hackernews
name: Hacker News
description: "Read Hacker News stories, comments, and discussions"
color: "#FF6600"
website: "https://news.ycombinator.com"
privacy_url: "https://www.ycombinator.com/legal#privacy"
terms_url: "https://www.ycombinator.com/legal"

test:
  list_posts:
    params:
      feed: front
      limit: 3
  get_post:
    params:
      id: '1'
      url: null
---

# Hacker News

Read Hacker News stories, comments, and discussions using the Algolia HN Search API.

## No Setup Required

This adapter uses the public Algolia HN Search API — no authentication needed.

## Why Algolia?

The official HN Firebase API requires multiple requests to fetch a story with comments (one per comment). Algolia returns the entire comment tree in a single request, making it much faster.

## Usage

| Operation | Description |
|-----------|-------------|
| `list_posts` | List stories by feed type (front, new, ask, show) |
| `search_posts` | Search stories by keyword |
| `get_post` | Get a single story with all comments |

## Feeds

The `list_posts` operation supports different feeds via the `feed` param:

| Feed | Description | HN URL |
|------|-------------|--------|
| `front` (default) | Front page / top stories | news.ycombinator.com |
| `new` | Newest submissions | news.ycombinator.com/newest |
| `ask` | Ask HN posts | news.ycombinator.com/ask |
| `show` | Show HN posts | news.ycombinator.com/show |

## Examples

```bash
# Front page stories (default)
POST /api/adapters/hackernews/post.list
{"limit": 30}

# Newest stories
POST /api/adapters/hackernews/post.list
{"feed": "new"}

# Ask HN posts
POST /api/adapters/hackernews/post.list
{"feed": "ask", "limit": 20}

# Show HN posts
POST /api/adapters/hackernews/post.list
{"feed": "show"}

# Search stories
POST /api/adapters/hackernews/post.search
{"query": "rust programming"}

# Get story with comments
POST /api/adapters/hackernews/post.get
{"id": "46826597"}
```

## Entity Aggregation

Stories also appear in aggregated endpoints:

```bash
# All posts from all sources
GET /api/posts

# Search across all sources
GET /api/posts/search?query=typescript
```
