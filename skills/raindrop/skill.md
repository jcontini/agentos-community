---
id: raindrop
name: Raindrop
description: Bookmark management
category: productivity

icon: https://raindrop.io/favicon.ico
color: "#0082FF"

abilities:
  - id: read_bookmarks
    label: "Read bookmarks and collections"
    endpoints:
      - "GET /rest/v1/collections"
      - "GET /rest/v1/collections/*"
      - "GET /rest/v1/raindrops/*"
      - "GET /rest/v1/raindrop/*"
      - "GET /rest/v1/tags"
  - id: save_bookmarks
    label: "Save new bookmarks"
    endpoints:
      - "POST /rest/v1/raindrop"
      - "POST /rest/v1/raindrops"
      - "PUT /rest/v1/raindrop/*"
      - "PUT /rest/v1/raindrops/*"
  - id: delete_bookmarks
    label: "Delete bookmarks"
    destructive: true
    endpoints:
      - "DELETE /rest/v1/raindrop/*"
      - "DELETE /rest/v1/raindrops/*"

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  help_url: https://app.raindrop.io/settings/integrations

api:
  base_url: https://api.raindrop.io
---

# Raindrop

**Use for:** Bookmark management, collections, saving links

## Quick Start

All requests go through the Passport proxy. Auth is automatic.

```bash
# List all collections
curl -s http://localhost:1111/cloud/raindrop/rest/v1/collections | jq '.items[] | {title, _id}'

# Get bookmarks in a collection
curl -s http://localhost:1111/cloud/raindrop/rest/v1/raindrops/COLLECTION_ID | jq '.items[] | {title, link}'

# Add a bookmark
curl -s -X POST http://localhost:1111/cloud/raindrop/rest/v1/raindrops \
  -H "Content-Type: application/json" \
  -d '{"link": "https://example.com", "collectionId": COLLECTION_ID}' | jq .
```

## API Reference

**Base URL:** `http://localhost:1111/cloud/raindrop`

### Collections

**GET /rest/v1/collections** - List all collections

**GET /rest/v1/collections/{id}** - Get collection by ID

**POST /rest/v1/collections** - Create collection
```json
{
  "title": "My Collection",
  "public": false
}
```

**Create nested collection:**
```json
{
  "title": "Subfolder",
  "parent": { "$id": PARENT_COLLECTION_ID },
  "public": false
}
```

### Bookmarks (Raindrops)

**GET /rest/v1/raindrops/{collection_id}** - List bookmarks in collection

**POST /rest/v1/raindrops** - Add bookmark
```json
{
  "link": "https://example.com",
  "title": "Optional custom title",
  "collectionId": 12345
}
```

**POST /rest/v1/raindrops/batch** - Add multiple bookmarks
```json
{
  "items": [
    { "link": "https://site1.com" },
    { "link": "https://site2.com" }
  ],
  "collectionId": 12345
}
```

**DELETE /rest/v1/raindrops/{id}** - Delete bookmark

### Special Collection IDs

| ID | Collection |
|----|------------|
| `0` | All bookmarks |
| `-1` | Unsorted |
| `-99` | Trash |

## Example Workflows

**Find collection ID by name:**
```bash
curl -s http://localhost:1111/cloud/raindrop/rest/v1/collections | \
  jq '.items[] | select(.title == "Research") | ._id'
```

**Save a link with tags:**
```bash
curl -s -X POST http://localhost:1111/cloud/raindrop/rest/v1/raindrops \
  -H "Content-Type: application/json" \
  -d '{
    "link": "https://example.com/article",
    "collectionId": 12345,
    "tags": ["reading", "tech"]
  }' | jq .
```

## Links

- [Raindrop API Docs](https://developer.raindrop.io)
