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
  dependency tree. Create, update, and complete plans via /mem/plans endpoints.
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

# Filter by computed status or priority
curl -s "http://localhost:3456/mem/plans?computed.status=ready&priority=now"

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
      "repository": "agentos"
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
- `data.repository` — which repo this belongs to

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
  -d '{ "done": true }'
```

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

Note: `from`/`to` use internal entity IDs (`_entity_id`), not service_ids. Query `/mem/plans` to find them.

## Plan Status

Status is computed from `done` and the enables graph — never set directly.

| Status | Meaning |
|--------|---------|
| `done` | Marked complete (`done: true`) |
| `blocked` | Has unfinished dependencies (incoming enables from undone plans) |
| `ready` | No blockers — can be worked on |

The response also includes `blocked_by` and `blocks` arrays (sourced from the enables graph) so you can see the full dependency chain.

## Repositories

Plans are grouped by repository via `data.repository`:

| Repository | Description |
|------------|-------------|
| `agentos` | Core engine roadmap |
| `agentos-community` | Skills, entities, apps roadmap |
| `entity-experiments` | Entity modeling experiments |
