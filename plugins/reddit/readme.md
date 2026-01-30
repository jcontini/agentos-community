---
id: reddit
name: Reddit
description: Read public Reddit communities, posts, and comments
icon: icon.png
color: "#FF4500"
tags: [social, reddit, communities]
display: browser

website: https://reddit.com
privacy_url: https://www.reddit.com/policies/privacy-policy
terms_url: https://www.redditinc.com/policies/user-agreement

sources:
  images:
    - styles.redditmedia.com
    - preview.redd.it
    - i.redd.it
    - external-preview.redd.it
    - a.thumbs.redditmedia.com
    - b.thumbs.redditmedia.com

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
      url: ".data.permalink | prepend: 'https://reddit.com'"
      author.name: .data.author
      author.url: ".data.author | prepend: 'https://reddit.com/u/'"
      community.name: .data.subreddit
      community.url: ".data.subreddit | prepend: 'https://reddit.com/r/'"
      engagement.score: .data.score
      engagement.comment_count: .data.num_comments
      published_at: ".data.created_utc | from_unix"
  
  group:
    terminology: Subreddit
    mapping:
      id: .name
      name: .display_name
      description: .public_description
      url: ".display_name | prepend: 'https://reddit.com/r/'"
      icon: .community_icon
      member_count: .subscribers
      member_count_numeric: .subscribers
      privacy: "OPEN"
      posts: .posts

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  post.search:
    description: Search posts across Reddit
    returns: post[]
    web_url: "https://www.reddit.com/search/?q={{params.query}}"
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 10, description: "Number of results (max 100)" }
      sort: { type: string, default: "relevance", description: "Sort by: relevance, hot, top, new, comments" }
    rest:
      method: GET
      url: https://www.reddit.com/search.json
      headers:
        User-Agent: "AgentOS/1.0"
      query:
        q: "{{params.query}}"
        limit: "{{params.limit | default:10}}"
        sort: "{{params.sort | default:relevance}}"
      response:
        root: "/data/children"

  post.list:
    description: List posts from a subreddit
    returns: post[]
    web_url: "https://www.reddit.com/r/{{params.subreddit}}"
    params:
      subreddit: { type: string, required: true, description: "Subreddit name (without r/)" }
      sort: { type: string, default: "hot", description: "Sort by: hot, new, top, rising" }
      limit: { type: integer, default: 25, description: "Number of posts (max 100)" }
    rest:
      method: GET
      url: "https://www.reddit.com/r/{{params.subreddit}}/{{params.sort | default:hot}}.json"
      headers:
        User-Agent: "AgentOS/1.0"
      query:
        limit: "{{params.limit | default:25}}"
      response:
        root: "/data/children"

  post.get:
    description: Get a Reddit post with comments
    returns: post
    web_url: "https://www.reddit.com/comments/{{params.id}}"
    params:
      id: { type: string, required: true, description: "Post ID (e.g., 'abc123')" }
      comment_limit: { type: integer, default: 100, description: "Max comments to fetch" }
    rest:
      method: GET
      url: "https://www.reddit.com/comments/{{params.id}}.json"
      headers:
        User-Agent: "AgentOS/1.0"
      query:
        limit: "{{params.comment_limit | default:100}}"
      response:
        root: "/0/data/children/0"

  group.get:
    description: Get a subreddit with its top posts
    returns: group
    web_url: "https://www.reddit.com/r/{{params.subreddit}}"
    params:
      subreddit: { type: string, required: true, description: "Subreddit name (without r/)" }
      limit: { type: integer, default: 25, description: "Number of posts to include" }
    command:
      binary: bash
      args:
        - "-c"
        - |
          SUBREDDIT="{{params.subreddit}}"
          LIMIT="{{params.limit | default:25}}"
          
          # Fetch subreddit metadata and posts
          ABOUT=$(curl -s -A "AgentOS/1.0" "https://www.reddit.com/r/${SUBREDDIT}/about.json")
          POSTS=$(curl -s -A "AgentOS/1.0" "https://www.reddit.com/r/${SUBREDDIT}/hot.json?limit=${LIMIT}")
          
          # Transform posts to entity format and combine with group metadata
          echo "$ABOUT" | jq --argjson posts "$(echo "$POSTS" | jq '[.data.children[] | {
            id: .data.id,
            title: .data.title,
            content: .data.selftext,
            url: ("https://reddit.com" + .data.permalink),
            author: { name: .data.author, url: ("https://reddit.com/u/" + .data.author) },
            community: { name: .data.subreddit, url: ("https://reddit.com/r/" + .data.subreddit) },
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

  group.search:
    description: Search for subreddits (communities)
    returns: group[]
    web_url: "https://www.reddit.com/subreddits/search/?q={{params.query}}"
    params:
      query: { type: string, required: true, description: "Search query" }
      limit: { type: integer, default: 10, description: "Number of results (max 100)" }
    rest:
      method: GET
      url: https://www.reddit.com/subreddits/search.json
      headers:
        User-Agent: "AgentOS/1.0"
      query:
        q: "{{params.query}}"
        limit: "{{params.limit | default:10}}"
      response:
        root: "/data/children"
---

# Reddit

Access public Reddit data using Reddit's built-in JSON endpoints.

## No Setup Required

Unlike the official Reddit API (which now requires pre-approval), this plugin uses Reddit's public JSON endpoints that work immediately without any configuration.

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
| `group.search` | Search for subreddits (communities) |
| `group.get` | Get metadata for a specific subreddit |

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
# Using plugin endpoints directly
POST /api/plugins/reddit/post.search
{"query": "rust programming", "limit": 10}

POST /api/plugins/reddit/post.list
{"subreddit": "programming", "sort": "hot"}

POST /api/plugins/reddit/post.get
{"id": "1abc234"}

# Search for subreddits
GET /api/groups/search?query=rust

# Get subreddit info
GET /api/groups/programming
```
