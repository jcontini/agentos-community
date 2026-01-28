---
id: reddit
name: Reddit
description: Read public Reddit communities, posts, and comments
icon: icon.png
tags: [social, communities]
display: browser

website: https://reddit.com
privacy_url: https://www.reddit.com/policies/privacy-policy
terms_url: https://www.redditinc.com/policies/user-agreement

instructions: |
  Reddit-specific notes:
  - Uses public JSON endpoints (no auth needed)
  - Rate limited to ~10 requests/minute
  - Works for any public subreddit, post, or user profile

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  # Post adapter - maps Reddit post data to unified post entity
  post:
    terminology: Post
    mapping:
      id: .data.id
      title: .data.title
      content: .data.selftext
      url: ".data.permalink | prepend: 'https://reddit.com'"
      author_name: .data.author
      author_url: ".data.author | prepend: 'https://reddit.com/user/'"
      community_name: .data.subreddit
      community_url: ".data.subreddit | prepend: 'https://reddit.com/r/'"
      score: .data.score
      comment_count: .data.num_comments
      published_at: ".data.created_utc | from_unix"

  # Comment adapter - maps Reddit comment data to post entity (comments are posts)
  comment:
    terminology: Comment
    mapping:
      id: .data.id
      content: .data.body
      url: ".data.permalink | prepend: 'https://reddit.com'"
      parent_id: ".data.parent_id | remove_prefix: 't1_' | remove_prefix: 't3_'"
      author_name: .data.author
      author_url: ".data.author | prepend: 'https://reddit.com/user/'"
      score: .data.score
      published_at: ".data.created_utc | from_unix"
      # Nested replies handled by transform

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  post.search:
    description: Search posts across Reddit
    returns: post[]
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
        adapter: post

  post.list:
    description: List posts from a subreddit
    returns: post[]
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
        adapter: post

  post.get:
    description: Get a Reddit post with nested comments
    returns: post
    params:
      id: { type: string, required: true, description: "Post ID (e.g., '1abc234')" }
      comment_limit: { type: integer, default: 100, description: "Max comments to fetch" }
    rest:
      method: GET
      url: "https://www.reddit.com/comments/{{params.id}}.json"
      headers:
        User-Agent: "AgentOS/1.0"
      query:
        limit: "{{params.comment_limit | default:100}}"
      response:
        # Reddit returns array: [0] = post, [1] = comments
        # Custom transform to build nested reply tree
        transform: |
          {
            id: .[0].data.children[0].data.id,
            title: .[0].data.children[0].data.title,
            content: .[0].data.children[0].data.selftext,
            url: ("https://reddit.com" + .[0].data.children[0].data.permalink),
            author: {
              name: .[0].data.children[0].data.author,
              url: ("https://reddit.com/user/" + .[0].data.children[0].data.author)
            },
            community: {
              name: .[0].data.children[0].data.subreddit,
              url: ("https://reddit.com/r/" + .[0].data.children[0].data.subreddit)
            },
            engagement: {
              score: .[0].data.children[0].data.score,
              comment_count: .[0].data.children[0].data.num_comments
            },
            published_at: (.[0].data.children[0].data.created_utc | todate),
            replies: [.[1].data.children[] | select(.kind == "t1") | {
              id: .data.id,
              content: .data.body,
              url: ("https://reddit.com" + .data.permalink),
              parent_id: (.data.parent_id | ltrimstr("t3_") | ltrimstr("t1_")),
              author: {
                name: .data.author,
                url: ("https://reddit.com/user/" + .data.author)
              },
              engagement: {
                score: .data.score
              },
              published_at: (.data.created_utc | todate),
              replies: (if .data.replies == "" then [] else [.data.replies.data.children[]? | select(.kind == "t1") | {
                id: .data.id,
                content: .data.body,
                parent_id: (.data.parent_id | ltrimstr("t1_")),
                author: { name: .data.author },
                engagement: { score: .data.score },
                published_at: (.data.created_utc | todate),
                replies: []
              }] end)
            }],
            has_more_replies: ([.[1].data.children[] | select(.kind == "more")] | length > 0)
          }
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
- `reddit.com/search.json?q=query` → search results

No authentication required, just a custom User-Agent header to avoid rate limiting.

## Rate Limits

- ~10 requests per minute without OAuth
- Sufficient for browsing and casual use

## Operations

| Operation | Description |
|-----------|-------------|
| `post.search` | Search posts across all of Reddit |
| `post.list` | List posts from a specific subreddit |
| `post.get` | Get a single post with nested comments |

## Response Structure

### post.list / post.search

Returns array of posts with unified schema:

```json
[
  {
    "id": "1abc234",
    "title": "Post title",
    "content": "Post body text",
    "url": "https://reddit.com/r/...",
    "author": { "name": "username", "url": "https://reddit.com/user/username" },
    "community": { "name": "programming", "url": "https://reddit.com/r/programming" },
    "engagement": { "score": 42, "comment_count": 15 },
    "published_at": "2026-01-27T12:00:00Z"
  }
]
```

### post.get

Returns post with nested reply tree:

```json
{
  "id": "1abc234",
  "title": "Post title",
  "content": "Post body text",
  "author": { "name": "username" },
  "community": { "name": "programming" },
  "engagement": { "score": 42, "comment_count": 15 },
  "replies": [
    {
      "id": "c1",
      "content": "First comment",
      "author": { "name": "commenter" },
      "engagement": { "score": 10 },
      "replies": [
        { "id": "c1a", "content": "Reply to comment", "replies": [] }
      ]
    }
  ],
  "has_more_replies": true
}
```

## Examples

```bash
# Search for posts about TypeScript
POST /api/plugins/reddit/post.search
{"query": "typescript tips", "limit": 10}

# List hot posts from r/programming  
POST /api/plugins/reddit/post.list
{"subreddit": "programming", "sort": "hot"}

# Get a specific post with comments
POST /api/plugins/reddit/post.get
{"id": "1abc234"}
```
