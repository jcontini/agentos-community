---
id: goodreads
name: Goodreads
description: Read your Goodreads profile, books, reviews, friends, and activity
icon: icon.svg
color: "#372213"
website: https://goodreads.com

connections:
  graphql:
    description: "Public AppSync GraphQL — API key auto-discovered from JS bundles"
  web:
    description: "Goodreads user cookies for viewer-scoped data"
    cookies:
      domain: ".goodreads.com"
      names: ["session_id", "__Secure-user_session"]
    optional: true
    label: Goodreads Session
    help_url: https://www.goodreads.com/user/sign_in

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS - Entity Mappings
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  account:
    id: .user_id
    name: .name
    handle: .username
    url: '"https://goodreads.com/user/show/" + (.user_id | tostring)'
    image: .photo_url
    text: .about
    location: .location
    data.books_count: .books_count
    data.ratings_count: .ratings_count
    data.avg_rating: .avg_rating
    data.reviews_count: .reviews_count
    data.website: .website
    data.birthday: .birthday
    data.joined_date: .joined_date
    data.favorite_genres: .favorite_genres

    favorite_books:
      book[]:
        _source: .favorite_books
        id: .book_id
        name: .title
        url: .web_url
        image: .cover_url
        author: .primary_author

    currently_reading:
      book[]:
        _source: .currently_reading
        id: .book_id
        name: .title
        url: .web_url
        image: .cover_url
        author: .primary_author

    shelves:
      shelf[]:
        _source: .shelves
        id: .shelf_id
        name: .name
        url: .url
        data.book_count: .book_count

  book:
    id: .book_id
    name: .title
    text: .description
    url: '.web_url // ("https://goodreads.com/book/show/" + (.book_id | tostring))'
    image: .cover_url
    author: .primary_author
    isbn: .isbn
    isbn13: .isbn13
    datePublished: .publication_date
    data.average_rating: .average_rating
    data.ratings_count: .ratings_count
    data.review_count: .review_count
    data.genres: .genres
    data.series: .series_name
    data.pages: .pages
    data.publisher: .publisher
    data.format: .format
    data.language: .language
    data.original_title: .original_title
    data.currently_reading_count: .currently_reading_count
    data.to_read_count: .to_read_count
    data.places: .places
    data.characters: .characters
    data.awards_won: .awards_won
    data.work_url: .work_url

    written_by:
      author:
        id: '.primary_author_id // .primary_author'
        name: .primary_author
        url: .primary_author_url

    contributors:
      author[]:
        _source: '.contributors // []'
        id: '.author_id // .name'
        name: .name
        url: .url
        image: .image_url
        data.role: .role

  review:
    id: .review_id
    name: '.title // ("Review of " + (.book_title // "book"))'
    text: .review_text
    url: '.review_url // ("https://goodreads.com/review/show/" + (.review_id | tostring))'
    author: .reviewer_name
    datePublished: .review_date
    engagement.rating: .rating
    engagement.likes: .likes_count
    data.comment_count: .comment_count
    data.tags: .tags
    data.shelf_name: .shelf_name
    
    posted_by:
      account:
        id: .reviewer_id
        name: .reviewer_name
        url: '.reviewer_url // ("https://goodreads.com/user/show/" + (.reviewer_id | tostring))'
        image: .reviewer_image_url
        data.followers_count: .reviewer_followers_count
        data.reviews_count: .reviewer_reviews_count

    references:
      book:
        id: .book_id
        name: .book_title
        url: '.book_url // ("https://goodreads.com/book/show/" + (.book_id | tostring))'

  author:
    id: .author_id
    name: .name
    text: .bio
    url: '"https://goodreads.com/author/show/" + (.author_id | tostring)'
    image: .photo_url
    location: .location
    data.average_rating: .average_rating
    data.works_count: .works_count
    data.birth_date: .birth_date
    data.website: .website
    data.twitter: .twitter
    data.member_since: .member_since
    data.followers_count: .followers_count

    books:
      book[]:
        _source: .books
        id: .book_id
        name: .title
        url: .web_url
        image: .cover_url
        author: .primary_author
        data.average_rating: .average_rating
        data.ratings_count: .ratings_count

  shelf:
    id: .shelf_id
    name: .name
    description: .description
    text: .description
    url: '"https://goodreads.com/shelf/show/" + (.shelf_id | tostring)'
    data.book_count: .book_count
    data.is_exclusive: .is_exclusive

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS - API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  # ───────────────────────────────────────────────────────────────────────────
  # PROFILE & USER OPERATIONS
  # ───────────────────────────────────────────────────────────────────────────
  
  get_profile:
    description: Get a public Goodreads profile and import bounded public relationships like favorite books, currently reading, and shelves
    returns: account
    connection: graphql
    params:
      user_id: { type: string, required: true, description: "User ID (e.g., '26631647')" }
      limit: { type: integer, default: 10, description: "Max related books or shelves to import per profile section" }
    python:
      module: ./public_graph.py
      function: get_public_profile
      args:
        user_id: .params.user_id
        limit: '.params.limit // 10'
      timeout: 15
    test:
      mode: read
      fixtures:
        user_id: "26631647"
        limit: 3

  search_people:
    description: Search for Goodreads users by name
    returns: account[]
    connection: graphql
    params:
      query: { type: string, required: true, description: "Name to search" }
      limit: { type: integer, default: 10, description: "Max results (default 10)" }
    rest:
      method: GET
      url: "https://www.goodreads.com/search/users"
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: text/html
      query:
        q: .params.query
      response:
        transform: |
          [.html | 
           scan("<a href=\"/user/show/([0-9]+)[^>]*>([^<]+)</a>") |
           {
             user_id: .[0],
             name: .[1]
           }] |
           .[0:.params.limit]
    test:
      mode: read
      fixtures:
        query: "Malcolm Gladwell"
        limit: 3

  list_friends:
    description: List a user's friends
    returns: account[]
    connection: graphql
    params:
      user_id: { type: string, required: true, description: "User ID" }
      page: { type: integer, default: 1, description: "Page number" }
    rest:
      method: GET
      url: '"https://www.goodreads.com/friend/user/" + .params.user_id'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: text/html
      query:
        page: .params.page
      response:
        transform: |
          [.html |
           scan("<div class=\"friendContainer[^>]*>.*?href=\"/user/show/([0-9]+)[^>]*>([^<]+)</a>") |
           {
             user_id: .[0],
             name: .[1]
           }]
    test:
      mode: read
      fixtures:
        user_id: "26631647"

  # ───────────────────────────────────────────────────────────────────────────
  # BOOK OPERATIONS
  # ───────────────────────────────────────────────────────────────────────────

  list_books:
    description: List a user's books organized by shelf (reading, want_to_read, read, did_not_finish)
    returns: book[]
    connection: graphql
    params:
      user_id: { type: string, required: true, description: "User ID" }
      shelf: { type: string, description: "Shelf: all, read, currently-reading, to-read, did-not-finish (default: all)" }
      sort: { type: string, default: "date_added", description: "Sort by: date_added, rating, title, author" }
      page: { type: integer, default: 1, description: "Page number" }
    rest:
      method: GET
      url: '"https://www.goodreads.com/review/list/" + .params.user_id'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: text/html
      query:
        shelf: '.params.shelf // "all"'
        sort: .params.sort
        page: .params.page
        per_page: "25"
      response:
        transform: |
          [.html | 
           scan("<tr[^>]*>.*?</tr>") |
           select(. != null) |
           {
             book_id: (match("book_id=([0-9]+)") | .captures[0].string | tonumber),
             title: (match("title=\"([^\"]+)\"") | .captures[0].string // ""),
             rating: (match("rating-\\d+") | .string | match("[0-9]") | .string | tonumber // 0)
           } |
           select(.book_id != null)] |
           .[0:25]
    test:
      mode: read
      fixtures:
        user_id: "26631647"
        shelf: read

  get_book:
    description: Get structured public book details from Goodreads hydration and Apollo state
    returns: book
    connection: graphql
    params:
      book_id: { type: string, required: true, description: "Book ID" }
    python:
      module: ./public_graph.py
      function: get_public_book
      args:
        book_id: .params.book_id
      timeout: 30
    test:
      mode: read
      fixtures:
        book_id: "4934"

  list_book_reviews:
    description: List public Goodreads reviews for a book via the AppSync GraphQL backend
    returns: review[]
    connection: graphql
    params:
      book_id: { type: string, required: true, description: "Book ID" }
      limit: { type: integer, default: 30, description: "Max reviews to return" }
    python:
      module: ./public_graph.py
      function: list_book_reviews
      args:
        book_id: .params.book_id
        limit: '.params.limit // 30'
      timeout: 30
    test:
      mode: read
      fixtures:
        book_id: "4934"
        limit: 3

  list_similar_books:
    description: List similar books from Goodreads' public AppSync GraphQL backend
    returns: book[]
    connection: graphql
    params:
      book_id: { type: string, required: true, description: "Book ID" }
      limit: { type: integer, default: 20, description: "Max similar books to return" }
    python:
      module: ./public_graph.py
      function: list_similar_books
      args:
        book_id: .params.book_id
        limit: '.params.limit // 20'
      timeout: 30
    test:
      mode: read
      fixtures:
        book_id: "4934"
        limit: 3

  list_series_books:
    description: List all books in a series, given any book that belongs to it
    returns: book[]
    connection: graphql
    params:
      book_id: { type: string, required: true, description: "Book ID of any book in the series" }
      limit: { type: integer, default: 20, description: "Max books to return" }
    python:
      module: ./public_graph.py
      function: list_series_books
      args:
        book_id: .params.book_id
        limit: '.params.limit // 20'
      timeout: 30
    test:
      mode: read
      fixtures:
        book_id: "3"
        limit: 5

  search_books:
    description: Search for books by title, author, or ISBN via the public AppSync GraphQL backend
    returns: book[]
    connection: graphql
    params:
      query: { type: string, required: true, description: "Search query (title, author, or ISBN)" }
      limit: { type: integer, default: 10, description: "Max results" }
    python:
      module: ./public_graph.py
      function: search_books
      args:
        query: .params.query
        limit: '.params.limit // 10'
      timeout: 15
    test:
      mode: read
      fixtures:
        query: "Brothers Karamazov"
        limit: 3

  get_author:
    description: Get a public Goodreads author profile and import bounded authored books
    returns: author
    connection: graphql
    params:
      author_id: { type: string, required: true, description: "Author ID" }
      limit: { type: integer, default: 10, description: "Max authored books to import" }
    python:
      module: ./public_graph.py
      function: get_public_author
      args:
        author_id: .params.author_id
        limit: '.params.limit // 10'
      timeout: 30
    test:
      mode: read
      fixtures:
        author_id: "3137322"
        limit: 3

  list_author_books:
    description: List a public Goodreads author's books
    returns: book[]
    connection: graphql
    params:
      author_id: { type: string, required: true, description: "Author ID" }
      limit: { type: integer, default: 10, description: "Max books to return" }
    python:
      module: ./public_graph.py
      function: parse_author_books
      args:
        author_id: .params.author_id
        limit: '.params.limit // 10'
      timeout: 30
    test:
      mode: read
      fixtures:
        author_id: "3137322"
        limit: 3

  # ───────────────────────────────────────────────────────────────────────────
  # REVIEW & RATING OPERATIONS
  # ───────────────────────────────────────────────────────────────────────────

  list_reviews:
    description: List your book reviews with ratings and dates
    returns: review[]
    connection: graphql
    params:
      user_id: { type: string, required: true, description: "User ID" }
      sort: { type: string, default: "date", description: "Sort by: date, rating, title" }
      page: { type: integer, default: 1, description: "Page number" }
    rest:
      method: GET
      url: '"https://www.goodreads.com/review/list/" + .params.user_id'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: text/html
      query:
        sort: .params.sort
        page: .params.page
        per_page: "25"
      response:
        transform: |
          [.html |
           scan("<tr[^>]*>.*?</tr>") |
           {
             review_id: (match("review_id=([0-9]+)") | .captures[0].string | tonumber),
             book_id: (match("book_id=([0-9]+)") | .captures[0].string | tonumber),
             book_title: (match("title=\"([^\"]+)\"") | .captures[0].string // ""),
             rating: (match("rating-([0-5])") | .captures[0].string | tonumber),
             review_date: (match("([0-9]{2}/[0-9]{2}/[0-9]{4})") | .captures[0].string // "")
           } |
           select(.review_id != null)] |
           .[0:25]
    test:
      mode: read
      fixtures:
        user_id: "26631647"

  # ───────────────────────────────────────────────────────────────────────────
  # SHELF OPERATIONS
  # ───────────────────────────────────────────────────────────────────────────

  list_shelves:
    description: List a user's bookshelves including default shelves (read, currently-reading, want-to-read)
    returns: shelf[]
    connection: graphql
    params:
      user_id: { type: string, required: true, description: "User ID" }
    rest:
      method: GET
      url: '"https://www.goodreads.com/user/shelves/" + .params.user_id'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: text/html
      response:
        transform: |
          [.html |
           scan("<a href=\"/review/list/[0-9]+-([^\"]+)[^>]*>([^<]+).*?\\(([0-9]+)\\)") |
           {
             shelf_id: .[0],
             name: .[1],
             book_count: (.[2] | tonumber)
           }]
    test:
      mode: read
      fixtures:
        user_id: "26631647"

  list_shelf_books:
    description: List books on a specific user shelf
    returns: book[]
    connection: graphql
    params:
      user_id: { type: string, required: true, description: "User ID" }
      shelf_name: { type: string, required: true, description: "Shelf name (e.g., 'read', 'currently-reading', 'to-read')" }
      page: { type: integer, default: 1, description: "Page number" }
    rest:
      method: GET
      url: '"https://www.goodreads.com/review/list/" + .params.user_id'
      headers:
        User-Agent: "Mozilla/5.0 (compatible; AgentOS/1.0)"
        Accept: text/html
      query:
        shelf: .params.shelf_name
        page: .params.page
        per_page: "25"
      response:
        transform: |
          [.html |
           scan("<tr[^>]*>.*?</tr>") |
           {
             book_id: (match("book_id=([0-9]+)") | .captures[0].string | tonumber),
             title: (match("title=\"([^\"]+)\"") | .captures[0].string // ""),
             author: (match("author_name\">([^<]+)") | .captures[0].string // "")
           } |
           select(.book_id != null)] |
           .[0:25]
    test:
      mode: read
      fixtures:
        user_id: "26631647"
        shelf_name: read

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

1. **Cache** — `.runtime-cache.json` with 1-hour TTL (instant)
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
