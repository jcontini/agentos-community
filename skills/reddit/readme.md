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

## Usage

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
