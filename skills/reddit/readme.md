---
id: reddit
name: Reddit
description: Read public Reddit communities, posts, and comments
icon: icon.png
color: "#FF4500"

website: https://reddit.com
privacy_url: https://www.reddit.com/policies/privacy-policy
terms_url: https://www.redditinc.com/policies/user-agreement

connections: {}

sources:
  images:
    - styles.redditmedia.com
    - preview.redd.it
    - i.redd.it
    - external-preview.redd.it
    - a.thumbs.redditmedia.com
    - b.thumbs.redditmedia.com
  image_headers:
    Referer: "https://www.reddit.com/"

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  post:
    id: .id
    name: .title
    title: .title
    text: .selftext // .body
    url: '"https://reddit.com" + .permalink'
    content: .selftext // .body
    author: .author
    datePublished: .created_utc | todate
    engagement.score: .score
    engagement.comment_count: .num_comments
    published_at: .created_utc | todate
    replies: .replies

    publish:
      community:
        id: .subreddit
        name: .subreddit
        url: '"https://reddit.com/r/" + .subreddit'
        platform: '"reddit"'

    posted_by:
      account:
        id: .author
        platform: '"reddit"'
        handle: .author
        display_name: .author
        url: '"https://reddit.com/u/" + .author'

    parent_id:
      ref: post
      value: .parent_id
      rel: replies_to

  community:
    id: .name
    name: .display_name
    description: .public_description
    url: '"https://reddit.com/r/" + .display_name'
    image: .community_icon
    icon: .community_icon
    member_count: .subscribers
    privacy: '"OPEN"'

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  search_posts:
    description: Search posts across Reddit
    returns: post[]
    web_url: '"https://www.reddit.com/search/?q=" + (.params.query | @uri)'
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, description: "Number of results (max 100)" }
      sort: { type: string, default: "relevance", description: "Sort by: relevance, hot, top, new, comments" }
    rest:
      method: GET
      url: https://www.reddit.com/search.json
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        q: .params.query
        limit: .params.limit
        sort: .params.sort
      response:
        transform: '[.data.children[] | .data]'
    test:
      mode: read

  list_posts:
    description: List posts from a subreddit
    returns: post[]
    web_url: '"https://www.reddit.com/r/" + .params.subreddit'
    params:
      subreddit: { type: string, required: true, description: "Subreddit name (without r/)" }
      sort: { type: string, default: "hot", description: "Sort by: hot, new, top, rising" }
      limit: { type: integer, description: "Number of posts (max 100)" }
    rest:
      method: GET
      url: '"https://www.reddit.com/r/" + .params.subreddit + "/" + .params.sort + ".json"'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        limit: .params.limit
      response:
        transform: '[.data.children[] | .data]'
    test:
      mode: read
      fixtures:
        subreddit: programming
        sort: hot
        limit: 3

  get_post:
    description: Get a Reddit post with comments
    returns: post
    web_url: '"https://www.reddit.com/comments/" + .params.id'
    params:
      id: { type: string, required: true, description: "Post ID (e.g., 'abc123')" }
      comment_limit: { type: integer, description: "Max comments to fetch" }
    rest:
      method: GET
      url: '"https://www.reddit.com/comments/" + .params.id + ".json"'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        limit: .params.comment_limit
      response:
        transform: |
          def map_comment:
            {
              id: .id,
              content: .body,
              posted_by: {
                account: {
                  id: .author,
                  platform: "reddit",
                  handle: .author,
                  display_name: .author,
                  url: ("https://reddit.com/u/" + .author)
                }
              },
              engagement: { score: .ups },
              published_at: (.created_utc | todate),
              replies: [if .replies == "" then empty else (.replies.data.children[] | select(.kind == "t1") | .data | map_comment) end]
            };
          .[0].data.children[0].data + {
            replies: [.[1].data.children[] | select(.kind == "t1") | .data | map_comment]
          }
    test:
      mode: read
      discover_from:
        op: list_posts
        params:
          subreddit: programming
          sort: hot
          limit: 3
        map:
          id: id

  comments_post:
    description: |
      Get comments on a Reddit post as graph-native entities.
      Returns a flat list: the parent post first, then all comments in parent-first order.
      Each comment becomes a post entity with replies_to relationship to its parent.
    returns: post[]
    web_url: '"https://www.reddit.com/comments/" + .params.id'
    params:
      id: { type: string, required: true, description: "Post ID (e.g., 'abc123')" }
      comment_limit: { type: integer, description: "Max comments to fetch" }
    command:
      binary: bash
      args:
        - ./comments_post.sh
        - ".params.id"
        - ".params.comment_limit"
      timeout: 30
    test:
      mode: read
      discover_from:
        op: list_posts
        params:
          subreddit: programming
          sort: hot
          limit: 3
        map:
          id: id

  get_community:
    description: Get subreddit metadata
    returns: community
    web_url: '"https://www.reddit.com/r/" + .params.subreddit'
    params:
      subreddit: { type: string, required: true, description: "Subreddit name (without r/)" }
    rest:
      method: GET
      url: '"https://www.reddit.com/r/" + .params.subreddit + "/about.json"'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      response:
        root: "/data"
    test:
      mode: read
      fixtures:
        subreddit: programming

  search_communities:
    description: Search for subreddits
    returns: community[]
    web_url: '"https://www.reddit.com/subreddits/search/?q=" + (.params.query | @uri)'
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, description: "Number of results (max 100)" }
    rest:
      method: GET
      url: https://www.reddit.com/subreddits/search.json
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        q: .params.query
        limit: .params.limit
      response:
        root: "/data/children"
    test:
      mode: read
---

# Reddit

Access public Reddit data using Reddit's built-in JSON endpoints.

## No Setup Required

Unlike the official Reddit API (which now requires pre-approval), this adapter uses Reddit's public JSON endpoints that work immediately without any configuration.

## How it works

Reddit exposes a public JSON API by simply appending `.json` to any URL:
- `reddit.com/r/programming.json` → subreddit posts
- `reddit.com/r/programming/new.json` → new posts
- `reddit.com/comments/{id}.json` → post with comments
- `reddit.com/search.json?q=query` → post search results
- `reddit.com/subreddits/search.json?q=query` → subreddit search results
- `reddit.com/r/{subreddit}/about.json` → subreddit metadata

No authentication required, just a custom User-Agent header to avoid rate limiting.

## Rate Limits

- ~10 requests per minute without OAuth
- Sufficient for browsing and casual use

## Operations

| Operation | Description |
|-----------|-------------|
| `search_posts` | Search posts across all of Reddit |
| `list_posts` | List posts from a specific subreddit |
| `get_post` | Get a single post with comments |
| `search_communities` | Search for subreddits |
| `get_community` | Get metadata for a specific subreddit |

## Examples

```bash
# Search for posts about TypeScript
GET /api/posts/search?query=typescript+tips

# List hot posts from r/programming  
GET /api/posts?subreddit=programming

# Get a specific post
GET /api/posts/abc123
```

```bash
# Using adapter endpoints directly
POST /api/adapters/reddit/post.search
{"query": "rust programming", "limit": 10}

POST /api/adapters/reddit/post.list
{"subreddit": "programming", "sort": "hot"}

POST /api/adapters/reddit/post.get
{"id": "1abc234"}

# Search for subreddits
GET /api/groups/search?query=rust

# Get subreddit info
GET /api/groups/programming
```
