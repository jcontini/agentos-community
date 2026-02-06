---
id: roadmap
name: Roadmap
extends: outcome
display:
  show_as_app: true
  icon: map
---

# Roadmap Skill

Track goals and dependencies across projects.

## Item Properties

Items have these fields in `data`:

| Field | Type | Description |
|-------|------|-------------|
| `timing` | string | Priority bucket: now, soon, later, someday |
| `title` | string | Display title |
| `description` | string | Markdown content |

Core fields (from outcome):

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier (slug) |
| `achieved` | datetime | When completed (null = not done) |

## Status (computed)

Status is derived from the enables graph:

| Status | Meaning |
|--------|---------|
| `done` | `achieved` date is set |
| `blocked` | Has unachieved dependencies |
| `ready` | Not done and not blocked |

## API

### List items

```http
GET /api/skills/roadmap/items
GET /api/skills/roadmap/items?timing=now
GET /api/skills/roadmap/items?status=ready
GET /api/skills/roadmap/items?timing=now&status=ready
```

### Create item

```http
POST /api/skills/roadmap/items
Content-Type: application/json

{
  "name": "entity-graph",
  "data": {
    "timing": "now",
    "title": "Entity Graph Schema",
    "description": "Build the entity graph..."
  }
}
```

### Get item

```http
GET /api/skills/roadmap/items/:name
```

Response includes computed status:

```json
{
  "id": "...",
  "name": "entity-graph",
  "data": { "timing": "now", "title": "..." },
  "status": "ready",
  "blocked_by": [],
  "enables": ["activity-backfill"]
}
```

### Update item

```http
PATCH /api/skills/roadmap/items/:name
Content-Type: application/json

{
  "data": {
    "timing": "soon",
    "description": "Updated content..."
  }
}
```

### Mark done

```http
PATCH /api/skills/roadmap/items/:name
Content-Type: application/json

{
  "data": {
    "achieved": "2026-02-05"
  }
}
```

### Delete item

```http
DELETE /api/skills/roadmap/items/:name
```

## Example Session

```
User: "What's ready to work on?"

Agent: GET /api/skills/roadmap/items?status=ready&timing=now
       → [boot-skill, dynamic-skills, ...]

User: "What's blocking chronicle?"

Agent: GET /api/skills/roadmap/items/chronicle
       → { status: "blocked", blocked_by: ["social-feed"] }
       
       "Chronicle is blocked by social-feed."

User: "Mark entity-graph as done"

Agent: PATCH /api/skills/roadmap/items/entity-graph
       { "data": { "achieved": "2026-02-05" } }
       
       "Done."
```
