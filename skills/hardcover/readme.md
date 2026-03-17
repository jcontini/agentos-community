---
id: hardcover
name: Hardcover
description: Search Hardcover books and sync your personal reading library through the Hardcover GraphQL API. Use when working with books on Hardcover or your reading status there.
icon: icon.svg
color: "#FF9100"
website: https://hardcover.app

auth:
  header:
    Authorization: .auth.key
  label: API Token
  help_url: https://hardcover.app/account/api

adapters:
  document:
    id: .id
    name: .title
    text: '.description // null'
    url: '.url // null'
    image: '.image // null'
    author: '.primary_author // null'
    datePublished: '.published_year // null'
    data.authors: '.authors // []'
    data.page_count: '.page_count // null'
    data.users_count: '.users_count // null'
    data.ratings_count: '.ratings_count // null'
    data.rating: '.rating // null'
    data.status: '.status // null'
    data.review: '.review // null'
    data.book_id: .book_id
    data.user_book_id: '.user_book_id // null'

operations:
  search_documents:
    description: Search Hardcover for books by title, author, or ISBN
    returns: document[]
    params:
      query:
        type: string
        required: true
        description: Search query
      limit:
        type: integer
        description: Maximum number of matches to return
    command:
      binary: python3
      args:
        - ./hardcover-api.py
        - search
      stdin: '{auth: .auth, params: (.params + {limit: (.params.limit // 5)})} | tojson'
      timeout: 45

  list_documents:
    description: List books from the authenticated user's Hardcover library
    returns: document[]
    params:
      limit:
        type: integer
        description: Maximum number of library entries to return
    command:
      binary: python3
      args:
        - ./hardcover-api.py
        - list
      stdin: '{auth: .auth, params: (.params + {limit: (.params.limit // 100)})} | tojson'
      timeout: 45

  get_document:
    description: Get a specific Hardcover book by Hardcover book id
    returns: document
    params:
      book_id:
        type: string
        required: true
        description: Hardcover book id
    command:
      binary: python3
      args:
        - ./hardcover-api.py
        - get
      stdin: '{auth: .auth, params: .params} | tojson'
      timeout: 45

  create_document:
    description: Add a Hardcover book to the authenticated user's library
    returns:
      ok: boolean
      user_book_id: string
      status: string
    params:
      book_id:
        type: string
        required: true
        description: Hardcover book id
      status:
        type: string
        description: want_to_read, reading, read, or dnf
    command:
      binary: python3
      args:
        - ./hardcover-api.py
        - add
      stdin: '{auth: .auth, params: .params} | tojson'
      timeout: 45

  update_document:
    description: Update reading status or rating for a library entry
    returns:
      ok: boolean
      user_book_id: string
      status: string
      rating: number
    params:
      user_book_id:
        type: string
        required: true
        description: Hardcover user_book id from list_documents
      status:
        type: string
        description: want_to_read, reading, read, or dnf
      rating:
        type: number
        description: Rating value to store on the library entry
    command:
      binary: python3
      args:
        - ./hardcover-api.py
        - update
      stdin: '{auth: .auth, params: .params} | tojson'
      timeout: 45

  delete_document:
    description: Remove a book from the authenticated user's Hardcover library
    returns:
      ok: boolean
      user_book_id: string
    params:
      user_book_id:
        type: string
        required: true
        description: Hardcover user_book id from list_documents
    command:
      binary: python3
      args:
        - ./hardcover-api.py
        - delete
      stdin: '{auth: .auth, params: .params} | tojson'
      timeout: 45
---

# Hardcover

Hardcover is a modern reading tracker with a GraphQL API. This first pass keeps the skill focused on the practical workflows that matter most:

- search for a book before acting
- inspect your current library entries
- add, update, or remove books in your library

## Setup

1. Get an API token from `https://hardcover.app/account/api`
2. Add it as the Hardcover credential in AgentOS

Important detail from Hardcover's docs: the API expects your token directly in the `authorization` header. It is not a `Bearer ...` token format.

## Recommended Workflow

1. Call `search_documents` with title plus author.
2. Confirm the match by author and year before mutating anything.
3. Use `create_document` with the returned `book_id`.
4. Use `list_documents` later to get `user_book_id` values for updates or deletes.

## Status Values

- `want_to_read`
- `reading`
- `read`
- `dnf`

## Notes

- The search path intentionally sorts by activity and popularity to surface the most likely canonical match first.
- Mutations work against Hardcover's `user_book` rows, so `update_document` and `delete_document` use `user_book_id`, not `book_id`.
- This skill maps books into `document` for now so it can pass the current contract cleanly without waiting on a dedicated book entity path.
