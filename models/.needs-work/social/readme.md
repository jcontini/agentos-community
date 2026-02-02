# Social Network App

A unified view of social networks — friends, feeds, profiles, activity.

## Vision

The Social app aggregates data from multiple social networks into one interface. Each network is just another plugin providing the same capabilities:

- **GitHub** — Developer social network
- **Twitter/X** — Tweets, follows
- **Bluesky/Mastodon** — Decentralized social
- **Instagram** — Photos, stories
- **Facebook** — Friends, posts, events
- **LinkedIn** — Professional network

The magic: **same data model, different sources**. A friend is a friend, whether from GitHub followers or Facebook friends.

---

## Capabilities

| Capability | Description |
|------------|-------------|
| `social.profile` | Get a user's social profile |
| `social.friends` | List friends/followers/connections |
| `social.activity` | Activity feed / timeline |
| `social.posts` | Posts/status updates from a user |
| `social.projects` | Projects/portfolio (GitHub repos, etc.) |

---

## Schemas

### `social.profile`

```typescript
// Input
{
  username: string,          // required
  network?: string           // which network (github, twitter, etc.)
}

// Output
{
  id: string
  name: string
  avatar: string             // url
  bio?: string
  location?: string
  website?: string
  joined?: string            // datetime
  followers_count?: number
  following_count?: number
  posts_count?: number
  network: string            // which network this came from
}
```

### `social.friends`

```typescript
// Input
{
  username: string,          // required
  type?: 'followers' | 'following' | 'mutual' | 'all',
  limit?: number
}

// Output
{
  friends: {
    id: string
    name: string
    avatar: string
    network: string
    relationship: string     // follower, following, mutual
  }[]
}
```

### `social.activity`

```typescript
// Input
{
  username?: string,         // if omitted, show feed from all followed users
  limit?: number
}

// Output
{
  activities: {
    id: string
    type: string             // post, share, like, comment, etc.
    author: {
      id: string
      name: string
      avatar: string
    }
    content?: string
    media?: string[]         // images, videos
    timestamp: string
    network: string
    likes_count?: number
    comments_count?: number
    shares_count?: number
  }[]
}
```

### `social.posts`

```typescript
// Input
{
  username: string,          // required
  limit?: number
}

// Output
{
  posts: {
    id: string
    content: string
    media?: string[]
    timestamp: string
    network: string
    likes_count?: number
    comments_count?: number
  }[]
}
```

---

## The Bigger Vision

This isn't just aggregation — it's **data ownership**:

1. **Import** your data from any network
2. **View** it all in one place
3. **Own** it locally (SQLite database)
4. **Export** to new formats
5. **Never lose** your social history again

Your social graph, posts, photos — all yours, forever, viewable through any theme.

---

## Example Connectors

- **GitHub** — Developer social network (API)
- **Twitter/X Archive** — Data export
- **Instagram** — Data export
- **Facebook** — Data export
- **LinkedIn** — Data export
- **Bluesky** — API
- **Mastodon** — API
