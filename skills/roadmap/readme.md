---
id: roadmap
name: Roadmap
description: AgentOS project roadmap — plans, priorities, and dependency graph
icon: icon.svg
color: "#6366F1"
platforms: [macos]

auth: none

transformers:
  plan:
    terminology: Roadmap Plan
    mapping:
      id: .id
      name: .name
      description: .description
      status: .status
      priority: .priority
      content: .content
      data.repository: .data.repository
      data.slug: .data.slug
      data.filepath: .data.filepath
      data.archived: .data.archived
      data.blocked_by: .data.blocked_by
      data.blocks: .data.blocks

operations:
  plan.list:
    description: List roadmap plans from a repository
    returns: plan[]
    params:
      repository:
        type: string
        default: all
        description: "Repository: agentos, agentos-community, entity-experiments, or all"
      status:
        type: string
        description: "Filter by status: ready, blocked, done"
      priority:
        type: string
        description: "Filter by priority: now, high"
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/roadmap/list-plans.py --repository {{params.repository}} --status {{params.status}} --priority {{params.priority}} --json 2>/dev/null"
      timeout: 30
---

# Roadmap

Reads `.ROADMAP/` directories and surfaces plan entities — features, initiatives, and specs with their dependency graph.

## How It Works

Plans live in `.ROADMAP/` directories across repositories. Each `.md` file becomes a plan entity, namespaced by repository (e.g. `agentos--desk`, `agentos-community--chatgpt-skill-spec`).

```
agentos/
  .ROADMAP/
    desk.md         → plan: agentos--desk (active)
    homepage.md     → plan: agentos--homepage (active)
    .archived/
      old-spec.md   → plan: agentos--old-spec (status: done)
```

Each `.md` file has YAML frontmatter declaring its priority and dependency edges:

```yaml
---
priority: now
blocked_by:
  - plan-entity
  - mcp-initialize-registration
blocks:
  - dynamic-docs
---

# Plan Title

Body text...
```

## Usage

```bash
# Import plans to graph (first time or refresh)
curl -H "X-Agent: cursor" "http://localhost:3456/mem/plans?refresh=true&skill=roadmap"

# Query from graph (fast, no re-pull)
curl -H "X-Agent: cursor" "http://localhost:3456/mem/plans"

# Filter by priority
curl -H "X-Agent: cursor" -X POST "http://localhost:3456/use/roadmap/plan.list" \
  -H "Content-Type: application/json" \
  -d '{"repository": "agentos", "priority": "now"}'
```

After entity import, run the migration script to create dependency relationships:

```bash
python3 ~/dev/agentos-community/scripts/roadmap-migrate.py --repository all --commit
```

## Plan Status

Status is computed from filesystem location and dependency state:

| Status | Meaning |
|--------|---------|
| `done` | File is in `.ROADMAP/.archived/` |
| `blocked` | Has unresolved `blocked_by` dependencies |
| `ready` | No blockers — can be worked on now |

## Repositories

| Slug | Path |
|------|------|
| `agentos` | `~/dev/agentos` |
| `agentos-community` | `~/dev/agentos-community` |
| `entity-experiments` | `~/dev/entity-experiments` |
| `all` | All three repositories |
