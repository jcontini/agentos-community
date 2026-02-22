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

connects_to: hackernews

seed:
  - id: hackernews
    types: [software]
    name: Hacker News
    data:
      software_type: platform
      url: https://news.ycombinator.com
      launched: "2007"
      platforms: [web]
      wikidata_id: Q686797
    relationships:
      - role: offered_by
        to: ycombinator

  - id: ycombinator
    types: [organization]
    name: Y Combinator
    data:
      type: company
      url: https://www.ycombinator.com
      founded: "2005"
      wikidata_id: Q2616400

instructions: |
  Hacker News notes:
  - Uses Algolia HN Search API (faster than official Firebase API)
  - No authentication required
  - Generous rate limits
  - Returns nested comments in single request

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  post:
    terminology: Story
    mapping:
      id: .objectID
      title: .title
      url: '"https://news.ycombinator.com/item?id=" + .objectID'
      content: .text
      external_url: .url
      replies: .replies
      
      engagement.score: .points
      engagement.comment_count: .num_comments
      published_at: .created_at
      
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
  post.list:
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
        default: 30
        description: "Number of stories (max 100)"
    rest:
      method: GET
      url: '"https://hn.algolia.com/api/v1/" + (if .params.feed == "new" then "search_by_date" else "search" end)'
      query:
        tags: '.params.feed | if . == "new" then "story" elif . == "ask" then "ask_hn" elif . == "show" then "show_hn" else "front_page" end'
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

  post.comments:
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
        - "-c"
        - |
          curl -s "https://hn.algolia.com/api/v1/items/{{params.id}}" | jq '
            def flatten_tree($parent_id):
              {objectID: (.id | tostring), text: .text, author: .author, created_at: .created_at, parent_id: $parent_id},
              (.children[]? | flatten_tree((.id | tostring)));
            (.id | tostring) as $story_id |
            [{objectID: $story_id, title: .title, text: .text, url: .url, author: .author, points: .points, num_comments: (.children | length), created_at: .created_at}]
            + [.children[]? | flatten_tree($story_id)]'
      timeout: 30
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
| `post.list` | List stories by feed type (front, new, ask, show) |
| `post.search` | Search stories by keyword |
| `post.get` | Get a single story with all comments |

## Feeds

The `post.list` operation supports different feeds via the `feed` param:

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
