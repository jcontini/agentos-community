---
id: todoist
name: Todoist
description: Personal task management - create, list, complete, update, delete tasks
category: productivity
icon: https://cdn.simpleicons.org/todoist
color: "#E44332"
protocol: shell

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "

requires:
  - curl  # Usually pre-installed
  - jq    # Usually pre-installed on macOS

actions:
  list_tasks:
    description: List tasks, optionally filtered by today/overdue/project
    params:
      filter:
        type: string
        description: Filter like "today", "overdue", "7 days", "no date"
      project_id:
        type: string
        description: Filter by project ID
    run: |
      URL="https://api.todoist.com/rest/v2/tasks"
      QUERY=""
      if [ -n "$PARAM_FILTER" ]; then
        QUERY="?filter=$(echo "$PARAM_FILTER" | jq -sRr @uri)"
      elif [ -n "$PARAM_PROJECT_ID" ]; then
        QUERY="?project_id=$PARAM_PROJECT_ID"
      fi
      curl -s "$URL$QUERY" \
        -H "Authorization: Bearer $AUTH_TOKEN" | \
      jq -r '.[] | "[\(.id)] \(.content) | Due: \(.due.date // "none") | Priority: \(.priority)"'

  get_task:
    description: Get a single task by ID, including its subtasks
    params:
      id:
        type: string
        required: true
        description: Task ID
    run: |
      echo "=== Task ==="
      curl -s "https://api.todoist.com/rest/v2/tasks/$PARAM_ID" \
        -H "Authorization: Bearer $AUTH_TOKEN" | jq .
      echo ""
      echo "=== Subtasks ==="
      curl -s "https://api.todoist.com/rest/v2/tasks?parent_id=$PARAM_ID" \
        -H "Authorization: Bearer $AUTH_TOKEN" | \
      jq -r '.[] | "  - [\(.id)] \(.content) | Due: \(.due.date // "none")"'

  create_task:
    description: Create a new task
    params:
      content:
        type: string
        required: true
        description: Task title/content
      due_string:
        type: string
        default: "today"
        description: Due date (today, tomorrow, next monday, 2025-01-15)
      priority:
        type: number
        description: Priority 1-4 (4 is urgent)
      project_id:
        type: string
        description: Project ID (cannot be changed after creation!)
      description:
        type: string
        description: Optional notes/description
      parent_id:
        type: string
        description: Parent task ID to create as subtask
    run: |
      # Build JSON payload
      PAYLOAD=$(jq -n \
        --arg content "$PARAM_CONTENT" \
        --arg due "${PARAM_DUE_STRING:-today}" \
        --arg priority "$PARAM_PRIORITY" \
        --arg project "$PARAM_PROJECT_ID" \
        --arg desc "$PARAM_DESCRIPTION" \
        --arg parent "$PARAM_PARENT_ID" \
        '{
          content: $content,
          due_string: $due,
          labels: ["AI"]
        }
        + (if $priority != "" then {priority: ($priority | tonumber)} else {} end)
        + (if $project != "" then {project_id: $project} else {} end)
        + (if $desc != "" then {description: $desc} else {} end)
        + (if $parent != "" then {parent_id: $parent} else {} end)')
      
      curl -s -X POST "https://api.todoist.com/rest/v2/tasks" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" | jq .

  update_task:
    description: Update a task (use POST not PUT!)
    params:
      id:
        type: string
        required: true
        description: Task ID to update
      content:
        type: string
        description: New task title
      due_string:
        type: string
        description: New due date (WARNING - see docs about recurring tasks!)
      priority:
        type: number
        description: New priority 1-4
      description:
        type: string
        description: New description/notes
    run: |
      # Build JSON payload with only provided fields
      PAYLOAD=$(jq -n \
        --arg content "$PARAM_CONTENT" \
        --arg due "$PARAM_DUE_STRING" \
        --arg priority "$PARAM_PRIORITY" \
        --arg desc "$PARAM_DESCRIPTION" \
        '{}
        + (if $content != "" then {content: $content} else {} end)
        + (if $due != "" then {due_string: $due} else {} end)
        + (if $priority != "" then {priority: ($priority | tonumber)} else {} end)
        + (if $desc != "" then {description: $desc} else {} end)')
      
      curl -s -X POST "https://api.todoist.com/rest/v2/tasks/$PARAM_ID" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" | jq .

  complete_task:
    description: Mark a task as complete
    params:
      id:
        type: string
        required: true
        description: Task ID to complete
    api:
      method: POST
      url: https://api.todoist.com/rest/v2/tasks/$PARAM_ID/close

  reopen_task:
    description: Reopen a completed task
    params:
      id:
        type: string
        required: true
        description: Task ID to reopen
    api:
      method: POST
      url: https://api.todoist.com/rest/v2/tasks/$PARAM_ID/reopen

  delete_task:
    description: Permanently delete a task
    params:
      id:
        type: string
        required: true
        description: Task ID to delete
    api:
      method: DELETE
      url: https://api.todoist.com/rest/v2/tasks/$PARAM_ID

  list_projects:
    description: List all projects
    api:
      method: GET
      url: https://api.todoist.com/rest/v2/projects

  list_labels:
    description: List all labels
    api:
      method: GET
      url: https://api.todoist.com/rest/v2/labels
---

# Todoist

Personal task management - create, list, complete, update, delete tasks.

## Requirements

This plugin requires `curl` and `jq` (usually pre-installed on macOS).

## Tools

### list_tasks
List tasks with optional filtering.

**Parameters:**
- `filter` (optional): Filter like "today", "overdue", "7 days"
- `project_id` (optional): Filter by project ID

**Examples:**
```
use-plugin(plugin: "todoist", tool: "list_tasks")
use-plugin(plugin: "todoist", tool: "list_tasks", params: {filter: "today"})
use-plugin(plugin: "todoist", tool: "list_tasks", params: {filter: "overdue"})
```

### get_task
Get a task by ID, including any subtasks.

**Parameters:**
- `id` (required): Task ID

**Example:**
```
use-plugin(plugin: "todoist", tool: "get_task", params: {id: "123456"})
```

### create_task
Create a new task. AI-created tasks are automatically labeled with "AI".

**Parameters:**
- `content` (required): Task title
- `due_string` (optional): Due date, default "today"
- `priority` (optional): 1-4 (4 is urgent)
- `project_id` (optional): Project ID (cannot change later!)
- `description` (optional): Notes
- `parent_id` (optional): Create as subtask

**Examples:**
```
use-plugin(plugin: "todoist", tool: "create_task", params: {content: "Buy groceries"})
use-plugin(plugin: "todoist", tool: "create_task", params: {content: "Urgent meeting", priority: 4, due_string: "tomorrow"})
```

### update_task
Update an existing task. Uses POST method (not PUT - Todoist quirk).

**Parameters:**
- `id` (required): Task ID
- `content` (optional): New title
- `due_string` (optional): New due date
- `priority` (optional): New priority
- `description` (optional): New notes

**Example:**
```
use-plugin(plugin: "todoist", tool: "update_task", params: {id: "123456", due_string: "tomorrow"})
```

### complete_task / reopen_task
Mark task complete or reopen it.

**Examples:**
```
use-plugin(plugin: "todoist", tool: "complete_task", params: {id: "123456"})
use-plugin(plugin: "todoist", tool: "reopen_task", params: {id: "123456"})
```

### delete_task
Permanently delete a task.

**Example:**
```
use-plugin(plugin: "todoist", tool: "delete_task", params: {id: "123456"})
```

### list_projects / list_labels
List all projects or labels.

**Examples:**
```
use-plugin(plugin: "todoist", tool: "list_projects")
use-plugin(plugin: "todoist", tool: "list_labels")
```

## ⚠️ Critical: Recurring Tasks

When updating a recurring task's due date, you MUST preserve the recurring pattern or it converts to a one-time task!

**Before updating due dates:**
1. First `get_task` to check if `is_recurring: true`
2. If recurring, preserve the pattern (e.g., "every saturday") or ask user

**Wrong (breaks recurring):**
```
update_task(id: "123", due_string: "today")  // Loses recurrence!
```

**Correct (preserves recurring):**
```
update_task(id: "123", due_string: "every saturday")  // Keeps recurrence
```

## ⚠️ Moving Tasks Between Projects

`project_id` cannot be updated after creation. To move a task:
1. Get task details
2. Delete old task
3. Create new task with new `project_id`

## Tips

- Priority: 1 = normal, 4 = urgent (counterintuitive!)
- AI-created tasks get `["AI"]` label automatically
- Use filters: "today", "overdue", "7 days", "no date"
- Always check for subtasks when getting a task
