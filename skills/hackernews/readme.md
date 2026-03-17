---
id: hackernews
name: Hacker News
description: Read Hacker News stories, comments, and discussions
icon: icon.png
color: "#FF6600"

website: https://news.ycombinator.com
privacy_url: https://www.ycombinator.com/legal#privacy
terms_url: https://www.ycombinator.com/legal

auth: none

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  post:
    id: .objectID
    name: .title
    text: .text
    url: '"https://news.ycombinator.com/item?id=" + .objectID'
    author: .author
    datePublished: .created_at
    external_url: .url
    replies: .replies
    engagement.score: .points
    engagement.comment_count: .num_comments
    posted_by:
      account:
        id: .author
        platform: '"hackernews"'
        handle: .author
        display_name: .author
        url: '"https://news.ycombinator.com/user?id=" + .author'
    parent_id:
      ref: post
      value: .parent_id
      rel: replies_to

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  list_posts:
    description: List Hacker News stories by feed type
    returns: post[]
    web_url: '"https://news.ycombinator.com/" + (if .params.feed == "front" then "" else .params.feed end)'
    params:
      feed:
        type: string
        default: "front"
        description: "Feed type: front, new, ask, show"
      limit:
        type: integer
        description: "Number of stories (max 100)"
    rest:
      method: GET
      url: '"https://hn.algolia.com/api/v1/" + (if .params.feed == "new" then "search_by_date" else "search" end)'
      query:
        tags: '.params.feed | if . == "new" then "story" elif . == "ask" then "ask_hn" elif . == "show" then "show_hn" else "front_page" end'
        hitsPerPage: .params.limit
      response:
        root: "/hits"
    test:
      mode: read
      fixtures:
        feed: front
        limit: 3

  search_posts:
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
        description: "Number of results (max 100)"
    rest:
      method: GET
      url: https://hn.algolia.com/api/v1/search
      query:
        query: .params.query
        tags: '"story"'
        hitsPerPage: .params.limit
      response:
        root: "/hits"
    test:
      mode: read

  get_post:
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
        transform: |
          def map_comment:
            {
              id: (.id | tostring),
              content: .text,
              posted_by: {
                account: {
                  id: .author,
                  platform: "hackernews",
                  handle: .author,
                  display_name: .author,
                  url: ("https://news.ycombinator.com/user?id=" + .author)
                }
              },
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
    test:
      mode: read
      discover_from:
        op: list_posts
        params:
          feed: front
          limit: 3
        map:
          id: id

  comments_post:
    description: |
      Get comments on a Hacker News story as graph-native entities.
      Returns a flat list: the parent story first, then all comments in parent-first order.
      Each comment becomes a post entity with replies_to relationship to its parent.
    returns: post[]
    web_url: '"https://news.ycombinator.com/item?id=" + .params.id'
    params:
      id:
        type: string
        required: true
        description: "Story ID"
    command:
      binary: bash
      args:
        - ./comments_post.sh
        - ".params.id"
      timeout: 30
    test:
      mode: read
      discover_from:
        op: list_posts
        params:
          feed: front
          limit: 3
        map:
          id: id
---

# Hacker News

Read Hacker News stories, comments, and discussions using the Algolia HN Search API.

## No Setup Required

This adapter uses the public Algolia HN Search API — no authentication needed.

## Why Algolia?

The official HN Firebase API requires multiple requests to fetch a story with comments (one per comment). Algolia returns the entire comment tree in a single request, making it much faster.

## Operations

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
