---
id: tasks
name: Tasks
description: Unified task management across all your tools
icon: material-symbols:check-circle
color: "#10B981"

schema:
  task:
    id:
      type: string
      required: true
      description: Unique identifier from the source system
    source_id:
      type: string
      description: Human-readable ID (e.g., "AGE-123" for Linear)
    title:
      type: string
      required: true
      description: Task title/content
    description:
      type: string
      description: Task description or notes (markdown supported)
    status:
      type: enum
      values: [open, in_progress, done, cancelled]
      required: true
      description: Current task status
    priority:
      type: number
      min: 1
      max: 4
      description: "Priority: 1=Urgent (P1), 2=High (P2), 3=Medium (P3), 4=Low (P4)"
    due:
      type: datetime
      description: Due date/time
    project:
      type: object
      properties:
        id: { type: string }
        name: { type: string }
      description: Project this task belongs to
    parent_id:
      type: string
      description: Parent task ID (for subtasks)
    labels:
      type: array
      items: { type: string }
      description: Tags or labels
    assignee:
      type: object
      properties:
        id: { type: string }
        name: { type: string }
      description: Person assigned to this task
    url:
      type: string
      description: Deep link to task in source system
    created_at:
      type: datetime
    updated_at:
      type: datetime
    # Advanced fields (optional, connector-specific)
    team:
      type: object
      properties:
        id: { type: string }
        name: { type: string }
      description: Team this task belongs to (Linear)
    cycle:
      type: object
      properties:
        id: { type: string }
        number: { type: number }
      description: Sprint/cycle this task is in (Linear)
    state:
      type: object
      properties:
        id: { type: string }
        name: { type: string }
        type: { type: string }
      description: Workflow state details (Linear)
    blocked_by:
      type: array
      items: { type: string }
      description: IDs of tasks blocking this one
    blocks:
      type: array
      items: { type: string }
      description: IDs of tasks this one blocks
    related:
      type: array
      items: { type: string }
      description: IDs of related tasks
    children:
      type: array
      items: { type: string }
      description: IDs of child tasks (subtasks)

  project:
    id:
      type: string
      required: true
    name:
      type: string
      required: true
    connector:
      type: string
      required: true
    account:
      type: string

actions:
  list:
    description: List tasks with optional filters
    readonly: true
    params:
      connector:
        type: string
        description: Filter by connector (todoist, linear)
      account:
        type: string
        description: Filter by account
      filter:
        type: string
        description: Filter expression (today, overdue, 7 days)
      project_id:
        type: string
        description: Filter by project ID
      status:
        type: string
        description: Filter by status (open, in_progress, done)
      limit:
        type: number
        default: 50
        description: Maximum tasks to return
    returns: task[]

  get:
    description: Get a single task by ID
    readonly: true
    params:
      id:
        type: string
        required: true
        description: Task ID
      connector:
        type: string
        required: true
        description: Which connector the task is from
    returns: task

  create:
    description: Create a new task
    params:
      title:
        type: string
        required: true
        description: Task title
      description:
        type: string
        description: Task description
      due:
        type: string
        description: Due date (today, tomorrow, 2025-01-15)
      priority:
        type: number
        description: "Priority: 0=Urgent, 1=High, 2=Medium, 3=Low"
      project_id:
        type: string
        description: Project ID
      parent_id:
        type: string
        description: Parent task ID (create as subtask)
      connector:
        type: string
        required: true
        description: Which connector to create in (todoist, linear)
      account:
        type: string
        description: Which account (if multiple)
    returns: task

  update:
    description: Update an existing task
    params:
      id:
        type: string
        required: true
        description: Task ID
      connector:
        type: string
        required: true
        description: Which connector the task is from
      title:
        type: string
        description: New title
      description:
        type: string
        description: New description
      due:
        type: string
        description: New due date
      priority:
        type: number
        description: New priority
      status:
        type: string
        description: New status
    returns: task

  complete:
    description: Mark a task as done
    params:
      id:
        type: string
        required: true
        description: Task ID
      connector:
        type: string
        required: true
        description: Which connector the task is from
    returns: task

  reopen:
    description: Reopen a completed task
    params:
      id:
        type: string
        required: true
        description: Task ID
      connector:
        type: string
        required: true
        description: Which connector the task is from
    returns: task

  delete:
    description: Permanently delete a task
    params:
      id:
        type: string
        required: true
        description: Task ID
      connector:
        type: string
        required: true
        description: Which connector the task is from
    returns: void

  move:
    description: Move a task to a different project
    params:
      id:
        type: string
        required: true
        description: Task ID to move
      project_id:
        type: string
        required: true
        description: Destination project ID
      connector:
        type: string
        required: true
        description: Which connector the task is from
    returns: task

  projects:
    description: List all projects
    readonly: true
    params:
      connector:
        type: string
        description: Filter by connector
      account:
        type: string
        description: Filter by account
    returns: project[]

  labels:
    description: List all labels/tags
    readonly: true
    params:
      connector:
        type: string
        description: Filter by connector
      account:
        type: string
        description: Filter by account
    returns:
      type: array
      items:
        id: { type: string }
        name: { type: string }
        color: { type: string }

  # Relationship actions (not all connectors support these)
  add_blocker:
    description: Set one task as blocking another (task cannot proceed until blocker is done)
    params:
      task_id:
        type: string
        required: true
        description: Task that is blocked
      blocker_id:
        type: string
        required: true
        description: Task that blocks (must be completed first)
      connector:
        type: string
        required: true
    returns: void

  remove_blocker:
    description: Remove a blocking relationship
    params:
      task_id:
        type: string
        required: true
        description: Task that was blocked
      blocker_id:
        type: string
        required: true
        description: Task that was blocking
      connector:
        type: string
        required: true
    returns: void

  add_related:
    description: Link two tasks as related
    params:
      task_id:
        type: string
        required: true
      related_id:
        type: string
        required: true
      connector:
        type: string
        required: true
    returns: void

  remove_related:
    description: Remove a related link between tasks
    params:
      task_id:
        type: string
        required: true
      related_id:
        type: string
        required: true
      connector:
        type: string
        required: true
    returns: void

instructions: |
  When working with tasks:
  - Use connector: "todoist" for personal tasks
  - Use connector: "linear" for work/engineering tasks
  - Always confirm before deleting tasks
  - For recurring tasks in Todoist, preserve the recurrence pattern when updating due dates
---

# Tasks

Unified task management across Todoist, Linear, and other task tools.

## Schema

The `task` entity represents a to-do item from any source with a normalized schema.

### Status Mapping

| Status | Todoist | Linear |
|--------|---------|--------|
| `open` | `is_completed: false` | state.type: `backlog`, `unstarted` |
| `in_progress` | - | state.type: `started` |
| `done` | `is_completed: true` | state.type: `completed` |
| `cancelled` | - | state.type: `canceled` |

### Priority Mapping

Normalized to 0-3 where **0 = Urgent (P0)**:

| Priority | Meaning | Todoist | Linear |
|----------|---------|---------|--------|
| 0 | Urgent (P0) | `priority: 4` | `priority: 1` |
| 1 | High (P1) | `priority: 3` | `priority: 2` |
| 2 | Medium (P2) | `priority: 2` | `priority: 3` |
| 3 | Low (P3) | `priority: 1` | `priority: 4` |

## Actions

### list

List tasks from one or all connectors.

```
tasks.list()                                    # All tasks from all connectors
tasks.list(connector: "todoist")                # Just Todoist
tasks.list(connector: "linear", account: "Adavia")  # Specific account
tasks.list(filter: "today")                     # Due today (Todoist filter)
tasks.list(status: "open")                      # Only open tasks
```

### get

Get a single task.

```
tasks.get(id: "123", connector: "todoist")
tasks.get(id: "abc-uuid", connector: "linear")
```

### create

Create a new task.

```
tasks.create(title: "Buy groceries", connector: "todoist")
tasks.create(title: "Fix bug", connector: "linear", account: "Adavia", priority: 4)
```

### complete / reopen

Mark tasks done or reopen them.

```
tasks.complete(id: "123", connector: "todoist")
tasks.reopen(id: "123", connector: "todoist")
```

### delete

Permanently delete a task.

```
tasks.delete(id: "123", connector: "todoist")
```

## Connectors

| Connector | Features | Notes |
|-----------|----------|-------|
| `todoist` | Full CRUD, filters, subtasks | Priority inverted from display |
| `linear` | Full CRUD, cycles, relations | Uses GraphQL |

## Tips

- Todoist supports rich filters: `today`, `overdue`, `7 days`, `no date`
- Linear issues have human-readable IDs like `AGE-123` in `source_id`
- Both support subtasks via `parent_id`
