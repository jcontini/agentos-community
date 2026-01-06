---
id: hardcover
name: Hardcover
description: Modern alternative to Goodreads for tracking your reading
icon: icon.png
website: https://hardcover.app

apps:
  - books

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: Authorization Header
  placeholder: "Bearer eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOi..."
  help_url: https://hardcover.app/account/api

# Action implementations (merged from mapping.yaml)
actions:
  pull:
    - graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          {
            me {
              user_books(
                where: {status_id: {_neq: 6}}
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
                  cached_contributors
                  cached_image
                }
              }
            }
          }
        response:
          root: "data.me[0].user_books"
          mapping:
            title: "[].book.title"
            authors: "[].book.cached_contributors[0].author.name | to_array"
            description: "[].book.description"
            page_count: "[].book.pages"
            published_year: "[].book.release_year"
            cover_url: "[].book.cached_image.url"
            status: |
              [].status_id == 1 ? 'want_to_read' :
              [].status_id == 2 ? 'reading' :
              [].status_id == 3 ? 'read' :
              [].status_id == 5 ? 'dnf' : 'none'
            rating: "[].rating | nullif:0"
            review: "[].review_raw"
            date_added: "[].date_added"
            hardcover_id: "[].book.id | to_string"
      as: records
    - app:
        action: upsert
        table: books
        data: "{{records}}"
        on_conflict:
          - hardcover_id

  push:
    - graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          query SearchBook($query: String!) {
            search(query: $query, query_type: "Book", per_page: 1, page: 1) {
              ids
            }
          }
        variables:
          query: "{{params.isbn || params.title}}"
        response:
          root: "data.search"
      as: search
    - graphql:
        endpoint: "https://api.hardcover.app/v1/graphql"
        query: |
          mutation AddBook($book_id: Int!, $status_id: Int!, $rating: Float) {
            insert_user_book(object: {
              book_id: $book_id, 
              status_id: $status_id,
              rating: $rating
            }) {
              id
            }
          }
        variables:
          book_id: "{{search.ids[0]}}"
          status_id: |
            {{params.status}} == 'read' ? 3 :
            {{params.status}} == 'reading' ? 2 :
            {{params.status}} == 'want_to_read' ? 1 :
            {{params.status}} == 'dnf' ? 5 : 1
          rating: "{{params.rating}}"
        response:
          root: "data.insert_user_book"
---

# Hardcover Connector

[Hardcover](https://hardcover.app) is a modern alternative to Goodreads for tracking your reading.

## Features

- **Pull**: Import your reading history from Hardcover
- **Push**: Export books from your local library to Hardcover

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

## Book Matching

When pushing books, we match by:
1. ISBN (preferred, most accurate)
2. Title search (fallback)

## Links

- [API Documentation](https://docs.hardcover.app/api/getting-started/)
- [GraphQL Console](https://cloud.hasura.io/public/graphiql?endpoint=https://api.hardcover.app/v1/graphql)
