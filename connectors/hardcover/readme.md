---
id: hardcover
name: Hardcover
description: Modern alternative to Goodreads for tracking your reading
icon: icon.svg
website: https://hardcover.app

auth:
  type: api_key
  header: authorization
  prefix: ""
  label: API Token
  help_url: https://hardcover.app/account/api
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
