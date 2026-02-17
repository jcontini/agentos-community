---
id: reddit
name: Reddit
description: Read public Reddit communities, posts, and comments
icon: icon.png
color: "#FF4500"

website: https://reddit.com
privacy_url: https://www.reddit.com/policies/privacy-policy
terms_url: https://www.redditinc.com/policies/user-agreement

auth: none
connects_to: reddit

sources:
  images:
    - styles.redditmedia.com
    - preview.redd.it
    - i.redd.it
    - external-preview.redd.it
    - a.thumbs.redditmedia.com
    - b.thumbs.redditmedia.com

seed:
  - id: reddit
    types: [software]
    name: Reddit
    data:
      software_type: platform
      url: https://reddit.com
      launched: "2005"
      platforms: [web, ios, android]
      wikidata_id: Q1136
    relationships:
      - role: offered_by
        to: reddit-inc

  - id: reddit-inc
    types: [organization]
    name: Reddit, Inc.
    data:
      type: company
      url: https://redditinc.com
      founded: "2005"
      ticker: RDDT
      exchange: NYSE
      wikidata_id: Q111759432

instructions: |
  Reddit-specific notes:
  - Uses public JSON endpoints (no auth needed)
  - Rate limited to ~10 requests/minute
  - Works for any public subreddit, post, or user profile

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  post:
    terminology: Post
    mapping:
      id: .data.id
      title: .data.title
      content: .data.selftext
      url: '"https://reddit.com" + .data.permalink'
      forum.name: .data.subreddit
      forum.url: '"https://reddit.com/r/" + .data.subreddit'
      engagement.score: .data.score
      engagement.comment_count: .data.num_comments
      published_at: .data.created_utc | todate
      replies: .replies
      
      # Typed reference: creates account entity and posts relationship
      # Uses raw API path — all mapping expressions reference raw data
      posted_by:
        account:
          id: .data.author
          platform: '"reddit"'
          handle: .data.author
          display_name: .data.author
          url: '"https://reddit.com/u/" + .data.author'
  
  forum:
    terminology: Subreddit
    mapping:
      id: .name
      name: .display_name
      description: .public_description
      url: '"https://reddit.com/r/" + .display_name'
      icon: .community_icon
      member_count: .subscribers
      member_count_numeric: .subscribers
      privacy: '"OPEN"'
      posts: .posts

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  post.search:
    description: Search posts across Reddit
    returns: post[]
    web_url: '"https://www.reddit.com/search/?q=" + (.params.query | @uri)'
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 10, description: "Number of results (max 100)" }
      sort: { type: string, default: "relevance", description: "Sort by: relevance, hot, top, new, comments" }
    rest:
      method: GET
      url: https://www.reddit.com/search.json
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        q: .params.query
        limit: .params.limit | tostring
        sort: .params.sort
      response:
        root: "/data/children"

  post.list:
    description: List posts from a subreddit
    returns: post[]
    web_url: '"https://www.reddit.com/r/" + .params.subreddit'
    params:
      subreddit: { type: string, required: true, description: "Subreddit name (without r/)" }
      sort: { type: string, default: "hot", description: "Sort by: hot, new, top, rising" }
      limit: { type: integer, default: 25, description: "Number of posts (max 100)" }
    rest:
      method: GET
      url: '"https://www.reddit.com/r/" + .params.subreddit + "/" + .params.sort + ".json"'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        limit: .params.limit | tostring
      response:
        root: "/data/children"

  post.get:
    description: Get a Reddit post with comments
    returns: post
    web_url: '"https://www.reddit.com/comments/" + .params.id'
    params:
      id: { type: string, required: true, description: "Post ID (e.g., 'abc123')" }
      comment_limit: { type: integer, default: 100, description: "Max comments to fetch" }
    rest:
      method: GET
      url: '"https://www.reddit.com/comments/" + .params.id + ".json"'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        limit: .params.comment_limit | tostring
      response:
        # Transform extracts post from .[0] and comments from .[1], mapping recursively
        # Output: { data: {post fields}, replies: [comments] } to match adapter mapping
        # Note: Reddit returns "" (empty string) for .replies when no nested replies exist
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
          {
            data: .[0].data.children[0].data,
            replies: [.[1].data.children[] | select(.kind == "t1") | .data | map_comment]
          }

  forum.get:
    description: Get a subreddit with its top posts
    returns: forum
    web_url: '"https://www.reddit.com/r/" + .params.subreddit'
    params:
      subreddit: { type: string, required: true, description: "Subreddit name (without r/)" }
      limit: { type: integer, default: 25, description: "Number of posts to include" }
    command:
      binary: bash
      args:
        - "-c"
        - |
          SUBREDDIT="{{params.subreddit}}"
          LIMIT="{{params.limit}}"
          
          # Fetch subreddit metadata and posts
          ABOUT=$(curl -s -A "AgentOS/1.0" "https://www.reddit.com/r/${SUBREDDIT}/about.json")
          POSTS=$(curl -s -A "AgentOS/1.0" "https://www.reddit.com/r/${SUBREDDIT}/hot.json?limit=${LIMIT}")
          
          # Transform posts to entity format and combine with group metadata
          echo "$ABOUT" | jq --argjson posts "$(echo "$POSTS" | jq '[.data.children[] | {
            id: .data.id,
            title: .data.title,
            content: .data.selftext,
            url: ("https://reddit.com" + .data.permalink),
            author: .data.author,
            forum: { name: .data.subreddit, url: ("https://reddit.com/r/" + .data.subreddit) },
            engagement: { score: .data.score, comment_count: .data.num_comments },
            published_at: (.data.created_utc | todate)
          }]')" '
          {
            name: .data.name,
            display_name: .data.display_name,
            public_description: .data.public_description,
            community_icon: .data.community_icon,
            subscribers: .data.subscribers,
            posts: $posts
          }
          '
      timeout: 30

  forum.search:
    description: Search for subreddits
    returns: forum[]
    web_url: '"https://www.reddit.com/subreddits/search/?q=" + (.params.query | @uri)'
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 10, description: "Number of results (max 100)" }
    rest:
      method: GET
      url: https://www.reddit.com/subreddits/search.json
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: application/json
      query:
        q: .params.query
        limit: .params.limit | tostring
      response:
        root: "/data/children"
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
| `post.search` | Search posts across all of Reddit |
| `post.list` | List posts from a specific subreddit |
| `post.get` | Get a single post with comments |
| `forum.search` | Search for subreddits |
| `forum.get` | Get metadata for a specific subreddit |

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
