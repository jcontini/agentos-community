---
id: hardcover
name: Hardcover
description: Modern alternative to Goodreads for tracking your reading
icon: icon.png
website: https://hardcover.app
tags: [books, reading, library]

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: Authorization Header
  placeholder: "Bearer eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOi..."
  help_url: https://hardcover.app/account/api

testing:
  exempt:
    credential_handling: "Stub test only checks readme action exists"
    cleanup: "Stub test does not test create operations"

actions:
  search:
    # Search for books on Hardcover, returns top matches sorted by popularity
    # Step 1: Search for books by query
    - operation: read
      graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          query SearchBooks($query: String!) {
            search(query: $query, query_type: "Book", per_page: 5, page: 1, sort: "activities_count:desc") {
              ids
            }
          }
        variables:
          query: "{{params.query}}"
      as: search
    # Step 2: Get book details for search results
    - operation: read
      graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          query GetBooks($ids: [Int!]!) {
            books(where: {id: {_in: $ids}}, order_by: {users_count: desc}) {
              id
              title
              slug
              description
              pages
              release_year
              users_count
              ratings_count
              rating
              cached_contributors
              image {
                url
              }
            }
          }
        variables:
          ids: "{{search.data.search.ids}}"
        response:
          root: "data.books"
          mapping:
            hardcover_id: "[].id | to_string"
            title: "[].title"
            authors: "[].cached_contributors[].author.name"
            description: "[].description"
            page_count: "[].pages"
            published_year: "[].release_year"
            cover_url: "[].image.url"
            url: "'https://hardcover.app/books/' + [].slug"
            users_count: "[].users_count"
            ratings_count: "[].ratings_count"
            rating: "[].rating"
            connector: "'hardcover'"

  pull:
    # Step 1: Get the authenticated user's ID
    - operation: read
      graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          {
            me {
              id
            }
          }
      as: user
    # Step 2: Get the user's books using their ID
    - operation: read
      graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          query GetUserBooks($user_id: Int!) {
            user_books(
              where: {user_id: {_eq: $user_id}, status_id: {_neq: 6}}
              order_by: {date_added: desc}
            ) {
              id
              rating
              status_id
              date_added
              reviewed_at
              review_raw
              book {
                id
                title
                slug
                description
                pages
                release_year
                image {
                  url
                }
                cached_contributors
              }
            }
          }
        variables:
          user_id: "{{user.data.me[0].id}}"
        response:
          root: "data.user_books"
          mapping:
            id: "[].id | to_string"
            title: "[].book.title"
            authors: "[].book.cached_contributors[].author.name"
            description: "[].book.description"
            page_count: "[].book.pages"
            published_year: "[].book.release_year"
            cover_url: "[].book.image.url"
            status: "[].status_id == '1' ? 'want_to_read' : [].status_id == '2' ? 'reading' : [].status_id == '3' ? 'read' : [].status_id == '5' ? 'dnf' : 'none'"
            rating: "[].rating | nullif:0"
            review: "[].review_raw"
            date_added: "[].date_added"
            hardcover_id: "[].book.id | to_string"
            connector: "'hardcover'"

  create:
    # Add a book by hardcover_id (from search results)
    # IMPORTANT: Always search first, verify with user, then create with the ID
    operation: create
    graphql:
      endpoint: "https://api.hardcover.app/v1/graphql"
      query: |
        mutation AddBook($book_id: Int!, $status_id: Int!) {
          insert_user_book(object: {
            book_id: $book_id, 
            status_id: $status_id
          }) {
            id
          }
        }
      variables:
        book_id: "{{params.hardcover_id | to_int}}"
        status_id: 1
      response:
        root: "data.insert_user_book"
        mapping:
          id: ".id | to_string"
          hardcover_id: "{{params.hardcover_id}}"
          status: "'want_to_read'"
          connector: "'hardcover'"

  update:
    # Update a book's status in Hardcover
    # Note: status_id mapping: 1=want_to_read, 2=reading, 3=read, 5=dnf
    operation: update
    graphql:
      endpoint: "https://api.hardcover.app/v1/graphql"
      query: |
        mutation UpdateUserBook($id: Int!, $status_id: Int, $rating: Float) {
          update_user_book(
            pk_columns: {id: $id}
            _set: {status_id: $status_id, rating: $rating}
          ) {
            id
            status_id
            rating
          }
        }
      variables:
        id: "{{params.id | to_int}}"
        status_id: "{{params.status_id | to_int}}"
        rating: "{{params.rating}}"
      response:
        root: "data.update_user_book"
        mapping:
          id: ".id | to_string"
          status: ".status_id == '1' ? 'want_to_read' : .status_id == '2' ? 'reading' : .status_id == '3' ? 'read' : .status_id == '5' ? 'dnf' : 'none'"
          rating: ".rating"
          connector: "'hardcover'"

  delete:
    # Remove a book from user's library
    operation: delete
    graphql:
      endpoint: "https://api.hardcover.app/v1/graphql"
      query: |
        mutation DeleteUserBook($id: Int!) {
          delete_user_book(id: $id) {
            id
          }
        }
      variables:
        id: "{{params.id | to_int}}"
      response:
        root: "data.delete_user_book"
        mapping:
          id: ".id | to_string"
          deleted: "'true'"

  push:
    # Push is for bulk operations - uses same logic as create
    # Step 1: Search for the book by title or ISBN, sorted by popularity
    - operation: read
      graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          query SearchBook($query: String!) {
            search(query: $query, query_type: "Book", per_page: 1, page: 1, sort: "activities_count:desc") {
              ids
            }
          }
        variables:
          query: "{{params.title | default: params.isbn}}"
      as: search
    # Step 2: Add the book to user's library
    - operation: create
      graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          mutation AddBook($book_id: Int!, $status_id: Int!) {
            insert_user_book(object: {
              book_id: $book_id, 
              status_id: $status_id
            }) {
              id
            }
          }
        variables:
          book_id: "{{search.data.search.ids[0] | to_int}}"
          status_id: 1
        response:
          root: "data.insert_user_book"
          mapping:
            id: ".id | to_string"
            connector: "'hardcover'"
---

# Hardcover Connector

[Hardcover](https://hardcover.app) is a modern alternative to Goodreads for tracking your reading.

## Features

- **Search**: Find books on Hardcover with popularity metrics
- **Pull**: Import your reading history from Hardcover
- **Create**: Add a single book to your Hardcover library
- **Update**: Change status, rating for existing books
- **Delete**: Remove a book from your library
- **Push**: Bulk export books to Hardcover

## Recommended Workflow for Adding Books

**IMPORTANT**: Always search first, verify the result matches user intent, then add by ID.

1. **Search** with title + author to see options
2. **Verify** the results match what the user asked for (correct author, title, etc.)
3. **If no match**: Tell the user what you found and ask if any work
4. **If match found**: Add by `hardcover_id` from search results

```
# Step 1: Search to see options
Books(action: "search", connector: "hardcover", params: {query: "Hackers Steven Levy"})
# Returns: [{hardcover_id: "380216", title: "Hackers", authors: ["Steven Levy"], users_count: 241}, ...]

# Step 2: Verify the author matches, then add by ID
Books(action: "create", connector: "hardcover", params: {hardcover_id: "380216"}, execute: true)
```

**Critical for AI agents**: 
- Do NOT add a book if the search results don't include the requested author
- If no matching author found, say: "I couldn't find a book by [author] with that title. Here's what I found: [results]. Do any of these work?"
- Only call `create` after confirming the `hardcover_id` matches user intent

## Authentication

1. Go to [Hardcover Account Settings > API](https://hardcover.app/account/api)
2. Copy your API token
3. Add to AgentOS credentials

## API Details

- **Endpoint**: `https://api.hardcover.app/v1/graphql`
- **Auth**: Bearer token in `authorization` header
- **Rate Limit**: 60 requests/minute, 30s timeout
- **Note**: API is in beta and may change

## Status Mapping

| AgentOS Status | Hardcover status_id |
|----------------|---------------------|
| want_to_read   | 1                   |
| reading        | 2                   |
| read           | 3                   |
| dnf            | 5                   |

## Usage Examples

```
# Search for a book (see popularity metrics)
Books(action: "search", connector: "hardcover", params: {query: "Dune Frank Herbert"})
# Returns results with hardcover_id, title, authors, users_count, ratings_count

# Add a book by ID (always search first to get the ID!)
Books(action: "create", connector: "hardcover", params: {hardcover_id: "380216"}, execute: true)

# Pull your Hardcover library
Books(action: "pull", connector: "hardcover", execute: true)

# Update a book's status
Books(action: "update", connector: "hardcover", params: {id: "123", status_id: 3}, execute: true)

# Delete a book from your library
Books(action: "delete", connector: "hardcover", params: {id: "123"}, execute: true)
```

## Notes

- **Search first, then create**: Never blindly add - always verify search results match user intent
- **Create** requires `hardcover_id` from search results - defaults to "want_to_read" status
- **Update** requires the user_book ID (from pull) and status_id (not status string)
- **Search** returns up to 5 results sorted by popularity - use `users_count` to pick the best one

## Links

- [API Documentation](https://docs.hardcover.app/api/getting-started/)
- [GraphQL Console](https://cloud.hasura.io/public/graphiql?endpoint=https://api.hardcover.app/v1/graphql)
