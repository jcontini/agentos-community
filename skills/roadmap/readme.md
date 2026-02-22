---
id: roadmap
name: Roadmap
description: AgentOS project roadmap — plans, priorities, and dependency graph
icon: icon.svg
color: "#6366F1"
platforms: [macos]
website: https://github.com/jcontini/agentos-community

auth: none

instructions: |
  The roadmap lives on the graph as plan entities. Use get_tree to see the
  dependency tree. Create, update, and archive plans via /mem/plans endpoints.
  Read the skill readme for full API examples.

utilities:
  get_tree:
    description: Render the roadmap as a dependency tree grouped by priority (NOW > HIGH > CONSIDERING)
    returns:
      tree: string
    command:
      binary: python3
      args:
        - "~/dev/agentos-community/skills/roadmap/tree-plans.py"
      timeout: 15
---

# Roadmap

The project roadmap lives on the graph as `plan` entities. Each plan represents a feature, initiative, or spec with priority, status, dependencies, and a markdown body.

Plans are namespaced by repository: `agentos--desk`, `agentos-community--chatgpt-skill-spec`.

## View the Roadmap

```bash
# Dependency tree (NOW > HIGH > CONSIDERING)
curl -s -X POST http://localhost:3456/use/roadmap/get_tree \
  -H "Content-Type: application/json" -d '{}'

# List all plans
curl -s http://localhost:3456/mem/plans

# Filter by status or priority
curl -s "http://localhost:3456/mem/plans?status=ready&priority=now"

# Full-text search over plan content
curl -s -X POST http://localhost:3456/mem/search \
  -H "Content-Type: application/json" \
  -d '{"query": "homepage", "types": ["plan"]}'
```

## Create a Plan

```bash
curl -s -X POST http://localhost:3456/mem/plans \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "agentos--my-new-feature",
    "name": "My New Feature",
    "description": "Short summary of what this is",
    "priority": "high",
    "content": "# My New Feature\n\nFull markdown spec goes here...",
    "data": {
      "repository": "agentos",
      "slug": "my-new-feature",
      "blocked_by": ["agentos--some-dependency"],
      "blocks": []
    }
  }'
```

**Required fields:**
- `service_id` — `{repository}--{slug}` format, must be unique
- `name` — human-readable title

**Optional fields:**
- `description` — one-line summary
- `priority` — `now` or `high` (omit for considering/unprioritized)
- `content` — full markdown body (FTS-indexed)
- `data.repository` — which roadmap this belongs to
- `data.blocked_by` — list of plan service_ids this depends on
- `data.blocks` — list of plan service_ids that depend on this

## Update a Plan

Use PATCH with the entity ID:

```bash
curl -s -X PATCH http://localhost:3456/mem/plans/<entity_id> \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My New Feature (Revised)",
    "priority": "now"
  }'
```

## Mark a Plan Done

```bash
curl -s -X PATCH http://localhost:3456/mem/plans/<entity_id> \
  -H "Content-Type: application/json" \
  -d '{ "data": { "archived": true } }'
```

Status is computed: `done` if archived, `blocked` if it has active blockers, `ready` otherwise.

## Add Dependencies

Dependencies use the `enables` relationship. If plan A must be done before plan B:

```bash
curl -s -X POST http://localhost:3456/mem/relate \
  -H "Content-Type: application/json" \
  -d '{
    "from": "<entity_id of plan A>",
    "to": "<entity_id of plan B>",
    "type": "enables"
  }'
```

Note: `from`/`to` use internal entity IDs (UUIDs), not service_ids. Query `/mem/plans` to find them.

## Plan Status

| Status | Meaning |
|--------|---------|
| `done` | Archived (`data.archived: true`) |
| `blocked` | Has unresolved dependencies |
| `ready` | No blockers — can be worked on |

## Repositories

Plans are grouped by repository via `data.repository`:

| Repository | Description |
|------------|-------------|
| `agentos` | Core engine roadmap |
| `agentos-community` | Skills, entities, apps roadmap |
| `entity-experiments` | Entity modeling experiments |
