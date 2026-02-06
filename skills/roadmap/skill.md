---
id: roadmap
name: Roadmap
description: Track project progress with tasks and dependencies
icon: mdi:map
extends: project
display:
  show_as_app: true
---

# Roadmap Skill

Track project milestones as tasks with priorities and blocking relationships.

## How It Works

A roadmap is a **project** with **tasks**. Each task has:
- `priority` (1=highest, 4=lowest) — what to work on next
- `blocked_by` — dependencies that must complete first
- `status` — open, in_progress, done, cancelled

## Priority Mapping

| Priority | Meaning | Old "timing" |
|----------|---------|--------------|
| 1 | Now — active work | `now` |
| 2 | Soon — next up | `soon` |
| 3 | Later — future work | `later` |
| 4 | Someday — backlog | `someday` |

## Status (Computed)

| Status | Meaning |
|--------|---------|
| `ready` | Not blocked, not done |
| `blocked` | Has incomplete blocking tasks |
| `done` | Completed |

## API

### List roadmap tasks

```http
GET /api/skills/roadmap/items
GET /api/skills/roadmap/items?priority=1
GET /api/skills/roadmap/items?status=ready
GET /api/skills/roadmap/items?priority=1&status=ready
```

### Create task

```http
POST /api/skills/roadmap/items
Content-Type: application/json

{
  "title": "Skill System",
  "description": "Build the skill loading infrastructure",
  "priority": 1
}
```

### Get task

```http
GET /api/skills/roadmap/items/:id
```

Response includes computed status:

```json
{
  "id": "...",
  "title": "Skill System",
  "priority": 1,
  "status": "ready",
  "blocked_by": [],
  "blocks": ["boot-skill"]
}
```

### Update task

```http
PATCH /api/skills/roadmap/items/:id
Content-Type: application/json

{
  "priority": 2,
  "description": "Updated content..."
}
```

### Complete task

```http
POST /api/skills/roadmap/items/:id/complete
```

### Add blocking relationship

```http
POST /api/skills/roadmap/items/:id/blockers
Content-Type: application/json

{
  "blocker_id": "other-task-id"
}
```

### Delete task

```http
DELETE /api/skills/roadmap/items/:id
```

## Example Session

```
User: "What's ready to work on?"

Agent: GET /api/skills/roadmap/items?status=ready&priority=1
       → [{ "title": "Skill System", "status": "ready", "priority": 1 }]

       "Skill System is ready — it's priority 1 with no blockers."

User: "What's blocking boot-skill?"

Agent: GET /api/skills/roadmap/items/boot-skill
       → { "status": "blocked", "blocked_by": ["skill-system"] }
       
       "Boot Skill is blocked by Skill System."

User: "Mark skill-system as done"

Agent: POST /api/skills/roadmap/items/skill-system/complete
       
       "Done. Boot Skill should now be unblocked."
```

## Future

- Link tasks to outcomes for higher-level goal tracking
- Progress tracking across linked tasks
- Multi-project roadmaps
