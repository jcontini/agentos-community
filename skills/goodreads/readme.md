---
id: goodreads
name: Goodreads
description: "Read your Goodreads profile, books, reviews, friends, and activity"
color: "#372213"
website: "https://goodreads.com"

connections:
  graphql:
    description: Public AppSync GraphQL — API key auto-discovered from JS bundles
  web:
    description: Goodreads user cookies for viewer-scoped data (friends, shelves, books, reviews)
    base_url: https://www.goodreads.com
    auth:
      type: cookies
      domain: .goodreads.com
      account:
        check: check_session
    optional: true
    label: Goodreads Session
    help_url: https://www.goodreads.com/user/sign_in

test:
  check_session:
    skip: true
  get_person:
    params:
      user_id: '26631647'
  search_people:
    skip: true
  resolve_email:
    skip: true
  list_friends:
    skip: true
  list_books:
    skip: true
  get_book:
    params:
      book_id: '4934'
  list_book_reviews:
    params:
      book_id: '4934'
      limit: 5
  list_similar_books:
    params:
      book_id: '4934'
      limit: 5
  list_series_books:
    params:
      book_id: '4934'
      limit: 5
  search_books:
    params:
      query: Brothers Karamazov
      limit: 3
  get_author:
    params:
      author_id: '3137322'
      limit: 3
  list_author_books:
    params:
      author_id: '3137322'
      limit: 3
  list_reviews:
    skip: true
  list_shelves:
    skip: true
  list_shelf_books:
    skip: true
  list_groups:
    skip: true
  list_following:
    skip: true
  list_followers:
    skip: true
  list_quotes:
    skip: true
---

# Goodreads Skill

Read your Goodreads profile, books, reviews, friends, and activity without needing an official API key.

## Setup

Goodreads discontinued their public API in 2020. This skill uses **session-based authentication** through your browser cookies.

### Quick Start

1. Sign in to [goodreads.com](https://www.goodreads.com)
2. Your session cookies will be automatically detected
3. Use operations for authenticated data (your profile, reviews, private shelves)
4. Public data (books, author profiles) works without login

## Features

### Profile & Social
- **`get_profile`** - User profile with stats, books count, location, photo
- **`search_people`** - Find users by name
- **`list_friends`** - Get a user's friends (public)

### Books
- **`list_books`** - Your books by shelf (reading, want to read, read)
- **`get_book`** - Structured public book details from Goodreads' hydrated page data
- **`list_similar_books`** - Similar books from Goodreads' public AppSync GraphQL backend
- **`search_books`** - Search all Goodreads books
- **`get_author`** - Author bio and works count
- **`list_book_reviews`** - Public GraphQL-backed reviews with reviewer accounts, shelves, tags, likes, and comments

### Reviews & Ratings
- **`list_reviews`** - Your reviews sorted by date, rating, or title
- **`list_book_reviews`** - Public reviews shown on a book page
- Ratings, likes, comments, shelves, and review dates included

### Shelves
- **`list_shelves`** - Your custom and default shelves
- **`list_shelf_books`** - Books on a specific shelf with count

## Data Model

All operations return data mapped to standard AgentOS entities:

| Entity | Represents | Fields |
|--------|------------|--------|
| **account** | User profiles | name, location, books_count, photo_url |
| **book** | Books | title, ISBN, author, genres, average_rating, pages |
| **review** | Book reviews | rating, review_text, review_date |
| **author** | Book authors | name, bio, average_rating, works_count |
| **shelf** | Book collections | name, book_count, description |

## Examples

```bash
# Get your profile
run({ skill: "goodreads", tool: "get_profile", params: { user_id: "26631647" } })

# List books you're currently reading
run({ skill: "goodreads", tool: "list_books", 
  params: { user_id: "26631647", shelf: "currently-reading", sort: "date_added" } })

# Search for a book
run({ skill: "goodreads", tool: "search_books", 
  params: { query: "Outliers Malcolm Gladwell", limit: 5 } })

# Get book details
run({ skill: "goodreads", tool: "get_book", params: { book_id: "3828382" } })

# List public reviews
run({ skill: "goodreads", tool: "list_book_reviews",
  params: { book_id: "4934", limit: 5 } })

# List similar books
run({ skill: "goodreads", tool: "list_similar_books",
  params: { book_id: "4934", limit: 5 } })

# View your reviews
run({ skill: "goodreads", tool: "list_reviews", 
  params: { user_id: "26631647", sort: "date" } })

# Find users
run({ skill: "goodreads", tool: "search_people", 
  params: { query: "Malcolm Gladwell", limit: 5 } })

# List your custom shelves
run({ skill: "goodreads", tool: "list_shelves", params: { user_id: "26631647" } })

# Get books on a specific shelf
run({ skill: "goodreads", tool: "list_shelf_books",
  params: { user_id: "26631647", shelf_name: "philosophy" } })
```

## Technical Details

### Authentication

The skill uses **Goodreads session cookies** from your browser for authenticated operations:

- `session_id` - Session token
- `__Secure-user_session` - Secure session token

These are automatically detected when you sign into Goodreads in your browser.

### Rate Limits

Goodreads has anti-bot protections:
- Recommended: 1-2 second delays between requests
- Public pages (books, authors) are typically less restricted
- Private pages (your reviews, feed) require valid session

### Data Freshness

- Profile data: Usually fresh within a few minutes
- Books/reviews: Real-time (cached by Goodreads ~15 min)
- Social graph: Updated when users make changes
- Ratings: Aggregated across millions of users (updated daily)

### Public Structured Sources

Goodreads has richer public data than the raw HTML suggests:

- Public **book pages** expose a large `__NEXT_DATA__` payload
- That payload contains an Apollo cache with structured book, work, contributor, and review data
- Public book pages also trigger AppSync GraphQL calls for related data such as similar books and reviews

This means the best public-first strategy is:

1. Use hydrated page data for stable public book and review reads
2. Keep older HTML scraping for profile, author, and search pages until those are replaced
3. Use GraphQL discovery to expand from the public book slice into similar books, quotes, shelves, and eventually authenticated views

### GraphQL Discovery

The AppSync endpoint and API key are **discovered at runtime**, not hardcoded. The discovery chain is:

1. **Graph Cache** — sandbox storage on the skill's graph node (instant, persisted across restarts)
2. **JS Bundle** — extract Prod config from the Next.js `_app` chunk (~1-2s, no browser needed)
3. **Browser Capture** — stealth Playwright watches AppSync network traffic (~15-20s fallback)
4. **Hardcoded Fallback** — known-good values as last resort

This means the skill self-heals when Goodreads rotates keys or redeploys.

## Scope Vision: Feature Parity with Reddit Skill

This skill is built to reach feature parity with the Reddit skill:

### Current Implementation
- Read user profiles and social connections (friends, followers)
- Access books across shelves (reading, want-to-read, read, custom)
- View reviews, ratings, and quotes
- Search books and people
- Get book and author metadata (ISBN, genres, ratings)
- Runtime AppSync discovery (no hardcoded API keys required)

### Future Enhancements
- Write operations (rate books, write reviews, add to shelves)
- Feed/activity stream (what friends are reading, recommendations)
- Reading statistics and yearly reading summaries
- Series and book recommendations
- Wishlist and reading challenges
- Groups and discussions
- Notes and highlights integration

### Why Reverse Engineering?

Goodreads has:
- **No official API** (discontinued 2020)
- **Hydrated Next.js public pages** with embedded Apollo state on book routes
- **GraphQL/AppSync backends** behind parts of the modern site
- **HTML-based legacy pages** for many profile and author views
- **Public JSON-LD metadata** (for SEO)
- **Session-based authentication** (no OAuth required)

This makes a mixed reverse-engineering approach the most reliable path today:

- structured public page parsing where Goodreads already hydrates data
- targeted HTML parsing for older pages
- JS bundle extraction for transport config (endpoint, API key)
- authenticated cookie-backed expansion for private shelves, feed, and social views
