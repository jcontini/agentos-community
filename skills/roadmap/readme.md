---
id: roadmap
name: Roadmap
description: AgentOS project roadmap — tasks, priorities, and dependency graph
icon: icon.svg
color: "#6366F1"
platforms: [macos]
website: https://github.com/jcontini/agentos-community

auth: none

instructions: |
  The roadmap lives on the graph as task entities. Use the Memex tools
  (list, search, get) to browse tasks by priority, status, and dependencies.
  Completion is a speech act — relate(from: actor_id, to: task_id, type: "completes").
---

# Roadmap

The project roadmap lives on the graph as `task` entities. Each task represents a feature, initiative, or spec with priority, status, dependencies, and a markdown body.

## Browse the Roadmap

```
list({ type: "task", priority: "now" })           What's active right now
list({ type: "task", priority: "high" })          Up next
list({ type: "task", done: false, limit: 50 })    All open tasks
search({ query: "homepage", types: ["task"] })     Full-text search
get({ id: "abc123", depth: 1 })                   Full detail + relationships
```

**Status** is computed from the graph — never set directly:

| Status | Meaning |
|--------|---------|
| `done` | Has a `completes` relationship from an actor |
| `blocked` | Has unfinished dependencies (incoming `enables` from undone tasks) |
| `ready` | No blockers — can be worked on |

## Create a Task

```
create({
  type: "task",
  name: "My New Feature",
  description: "Short summary",
  priority: "now",
  content: "# My New Feature\n\nFull markdown spec goes here..."
})
```

**Required:** `name`
**Optional:** `description`, `priority` (`now` or `high`), `content` (full markdown body, FTS-indexed)

## Update a Task

```
update({ id: "abc123", name: "Revised Name", priority: "now" })
```

## Mark a Task Done

Completion is a speech act — an actor declares the task done:

```
relate({ from: "ddadc30e", to: "task_id", type: "completes" })
```

To reopen:

```
relate({ from: "ddadc30e", to: "task_id", type: "reopens" })
```

## Add Dependencies

If task A must be done before task B:

```
relate({ from: "task_a_id", to: "task_b_id", type: "enables" })
```

The `blocked_by` and `blocks` arrays on each task are computed from the `enables` graph.

## Roadmap in the README

The main README template renders the roadmap live using Bahasa:

```jinja
{% set now_tasks = from("task", priority="now", limit=20) %}
{% set high_tasks = from("task", priority="high", limit=10) %}
```

This pulls directly from the Memex — no bespoke code, no caching, always current.
