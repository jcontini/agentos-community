---
id: hackernews
name: Hacker News
description: Read Hacker News stories, comments, and discussions
icon: icon.svg
color: "#FF6600"
tags: [news, tech, communities]
display: browser

website: https://news.ycombinator.com
privacy_url: https://www.ycombinator.com/legal#privacy
terms_url: https://www.ycombinator.com/legal

instructions: |
  Hacker News notes:
  - Uses Algolia HN Search API (faster than official Firebase API)
  - No authentication required
  - Generous rate limits
  - Returns nested comments in single request

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  post:
    terminology: Story
    mapping:
      # Search results use objectID, item endpoint uses id
      id: .objectID
      title: .title
      content: .text
      url: '"https://news.ycombinator.com/item?id=" + .objectID'
      external_url: .url
      author.name: .author
      author.url: '"https://news.ycombinator.com/user?id=" + .author'
      engagement.score: .points
      engagement.comment_count: .num_comments
      published_at: .created_at
      replies: .replies

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  post.list:
    description: List front page stories from Hacker News
    returns: post[]
    web_url: https://news.ycombinator.com
    params:
      limit:
        type: integer
        default: 30
        description: "Number of stories (max 100)"
    rest:
      method: GET
      url: https://hn.algolia.com/api/v1/search
      query:
        tags: front_page
        hitsPerPage: .params.limit | tostring
      response:
        root: "/hits"

  post.list_new:
    description: List newest stories from Hacker News
    returns: post[]
    web_url: https://news.ycombinator.com/newest
    params:
      limit:
        type: integer
        default: 30
        description: "Number of stories (max 100)"
    rest:
      method: GET
      url: https://hn.algolia.com/api/v1/search_by_date
      query:
        tags: story
        hitsPerPage: .params.limit | tostring
      response:
        root: "/hits"

  post.list_ask:
    description: List Ask HN posts
    returns: post[]
    web_url: https://news.ycombinator.com/ask
    params:
      limit:
        type: integer
        default: 30
        description: "Number of posts (max 100)"
    rest:
      method: GET
      url: https://hn.algolia.com/api/v1/search
      query:
        tags: ask_hn
        hitsPerPage: .params.limit | tostring
      response:
        root: "/hits"

  post.list_show:
    description: List Show HN posts
    returns: post[]
    web_url: https://news.ycombinator.com/show
    params:
      limit:
        type: integer
        default: 30
        description: "Number of posts (max 100)"
    rest:
      method: GET
      url: https://hn.algolia.com/api/v1/search
      query:
        tags: show_hn
        hitsPerPage: .params.limit | tostring
      response:
        root: "/hits"

  post.search:
    description: Search Hacker News stories
    returns: post[]
    web_url: '"https://hn.algolia.com/?query=" + (.params.query | @uri)'
    params:
      query:
        type: string
        required: true
        description: "Search query"
      limit:
        type: integer
        default: 20
        description: "Number of results (max 100)"
    rest:
      method: GET
      url: https://hn.algolia.com/api/v1/search
      query:
        query: .params.query
        tags: '"story"'
        hitsPerPage: .params.limit | tostring
      response:
        root: "/hits"

  post.get:
    description: Get a Hacker News story with comments
    returns: post
    web_url: '"https://news.ycombinator.com/item?id=" + .params.id'
    params:
      id:
        type: string
        required: true
        description: "Story ID"
    rest:
      method: GET
      url: '"https://hn.algolia.com/api/v1/items/" + .params.id'
      response:
        # Transform reshapes to match adapter expectations
        # Adapter expects .objectID, but items endpoint returns .id
        # Output shape: fields adapter can map + pre-mapped replies
        transform: |
          def map_comment:
            {
              id: (.id | tostring),
              content: .text,
              author: { name: .author, url: ("https://news.ycombinator.com/user?id=" + .author) },
              published_at: .created_at,
              replies: [.children[]? | map_comment]
            };
          {
            objectID: (.id | tostring),
            title: .title,
            text: .text,
            url: .url,
            author: .author,
            points: .points,
            num_comments: (.children | length),
            created_at: .created_at,
            replies: [.children[]? | map_comment]
          }
---

# Hacker News

Read Hacker News stories, comments, and discussions using the Algolia HN Search API.

## No Setup Required

This plugin uses the public Algolia HN Search API — no authentication needed.

## Why Algolia?

The official HN Firebase API requires multiple requests to fetch a story with comments (one per comment). Algolia returns the entire comment tree in a single request, making it much faster.

## Operations

| Operation | Description |
|-----------|-------------|
| `post.list` | Front page stories |
| `post.list_new` | Newest stories |
| `post.list_ask` | Ask HN posts |
| `post.list_show` | Show HN posts |
| `post.search` | Search stories by keyword |
| `post.get` | Get a single story with all comments |

## Examples

```bash
# Front page stories
POST /api/plugins/hackernews/post.list
{"limit": 30}

# Newest stories
POST /api/plugins/hackernews/post.list_new
{}

# Ask HN posts
POST /api/plugins/hackernews/post.list_ask
{}

# Show HN posts
POST /api/plugins/hackernews/post.list_show
{}

# Search stories
POST /api/plugins/hackernews/post.search
{"query": "rust programming"}

# Get story with comments
POST /api/plugins/hackernews/post.get
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
