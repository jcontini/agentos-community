---
id: roadmap
name: Roadmap
description: Dependency-driven project planning

views:
  planned:
    name: Planned
    filter:
      completed: false
      priority_lte: 2
    include: [blocked_by, blocks]
    layout: dependency-graph
    sort_by: priority

  backlog:
    name: Backlog
    filter:
      completed: false
      priority_gte: 3
    include: [blocked_by, blocks]
    layout: dependency-graph
    sort_by: priority

  archive:
    name: Archive
    filter:
      completed: true
    layout: list
    sort_by: completed_at
---

# Roadmap Skill

Track project milestones as tasks with priorities and blocking relationships.

## How It Works

A roadmap is a **project** labeled `roadmap` with **tasks**. Each task has:
- `priority` (1=highest, 4=lowest) — what to work on next
- `blocked_by` — dependencies that must complete first
- `status` — computed: ready, blocked, or done

## Priority Mapping

| Priority | Meaning |
|----------|---------|
| 1 | Now — active work |
| 2 | Soon — next up |
| 3 | Later — future work |
| 4 | Someday — backlog |

## Status (Computed)

| Status | Meaning |
|--------|---------|
| `ready` | Not blocked, not done |
| `blocked` | Has incomplete blocking tasks |
| `done` | Completed |

## API

### List tasks (with views)

```http
GET /api/tasks?view=roadmap.planned
GET /api/tasks?view=roadmap.backlog
GET /api/tasks?view=roadmap.archive
```

### Without views (manual filters)

```http
GET /api/tasks?priority=1&completed=false
GET /api/tasks?priority=1,2&computed.status=ready
GET /api/tasks?project=agentos&include=blocked_by
```

### Create task

```http
POST /api/tasks
Content-Type: application/json

{
  "title": "Skill System",
  "description": "Build the skill loading infrastructure",
  "priority": 1,
  "project_id": "agentos"
}
```

### Complete task

```http
POST /api/tasks/{id}/complete
```

## Views

### Planned
Priority 1-2 tasks that aren't done. Shows dependency graph — see what's ready and what's blocked.

### Backlog
Priority 3-4 tasks. Also shows dependency graph for future planning.

### Archive
Completed tasks, sorted by completion date.

## Example Session

```
User: "What's ready to work on?"

Agent: GET /api/tasks?view=roadmap.planned&computed.status=ready
       → [{ "title": "Skill System", "status": "ready", "priority": 1 }]

       "Skill System is ready — it's priority 1 with no blockers."

User: "What's blocking boot-skill?"

Agent: GET /api/tasks/boot-skill?include=blocked_by
       → { "status": "blocked", "blocked_by": [{"name": "skill-system"}] }
       
       "Boot Skill is blocked by Skill System."

User: "Mark skill-system as done"

Agent: POST /api/tasks/skill-system/complete
       
       "Done. Boot Skill should now be unblocked."
```

## Future

- Link tasks to outcomes for higher-level goal tracking
- Progress tracking across linked tasks
- Multi-project roadmaps
