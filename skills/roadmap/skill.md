# Roadmap Skill

Track goals and dependencies across projects using the outcome entity.

## What This Skill Does

The roadmap skill extends the `outcome` entity for project planning:

- **Intentions** (outcomes) represent goals or specs to complete
- **Timing** (now/soon/later/someday) buckets priorities
- **Status** (ready/blocked/done) computed from dependencies
- **Enables** relationships show what blocks what

## Querying the Roadmap

### What's ready to work on?

```http
GET /api/outcomes?status=ready&data.timing=now
```

Returns unblocked items in the NOW bucket.

### What's blocking something?

```http
GET /api/outcomes/:name
```

Response includes `enablers` (what must be done first) and `status`.

### Recently completed

```http
GET /api/outcomes?status=done&include_archived=true
```

## Timing Values

| Timing | Meaning |
|--------|---------|
| `now` | Current focus, actively working |
| `soon` | Next up after current work |
| `later` | Planned but not prioritized |
| `someday` | Ideas, maybe never |

## Status Computation

Status is derived from the enables graph:

```
status = 
  if achieved != null → "done"
  else if all enablers achieved → "ready"  
  else → "blocked"
```

**Block reason:** Names of enablers that aren't achieved yet.

## Editing Workflow

### With terminal access (Cursor, CLI)

1. Fetch the intention as markdown:
   ```http
   GET /api/outcomes/:name?format=markdown
   ```

2. Save to temp file and edit with native tools

3. Push back:
   ```http
   POST /api/outcomes/:name
   { "description": "updated markdown content" }
   ```

### Without terminal access

Edit the description field directly via API.

## Archiving

To mark an intention as done:

```http
POST /api/outcomes/:name/archive
```

Sets `achieved` to current date. Done items don't appear in default queries.

## Multiple Roadmaps

Intentions can belong to different roadmaps:

- AgentOS roadmap
- Adavia roadmap  
- Personal goals

Use the `belongs_to` relationship to organize:

```http
GET /api/outcomes?roadmap=agentos
```

## Example Session

```
User: "What's ready to work on?"

Agent: GET /api/outcomes?status=ready&data.timing=now
       → [boot-skill, dynamic-skills, clear-history, ...]

User: "What's blocking chronicle?"

Agent: GET /api/outcomes/chronicle
       → { status: "blocked", enablers: ["social-feed"] }
       
       "Chronicle is blocked by social-feed, which needs to be done first."

User: "Archive entity-graph, it's done"

Agent: POST /api/outcomes/entity-graph/archive
       → { achieved: "2026-02-05" }
       
       "Done. entity-graph marked as complete."
```
