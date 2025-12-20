---
id: todoist
name: Todoist
description: Personal task management - create, list, complete, update, delete tasks
icon: https://cdn.simpleicons.org/todoist
color: "#E44332"

website: https://todoist.com
privacy_url: https://doist.com/privacy
terms_url: https://doist.com/terms-of-service

tags: [tasks, to-dos, reminders]

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: API Token
  help_url: https://todoist.com/help/articles/find-your-api-token-Jpzx9IIlB

# No shell dependencies - all actions use secure REST executor

actions:
  get_tasks:
    readonly: true
    description: List tasks with optional filters. Use parent_id to get subtasks.
    params:
      filter:
        type: string
        description: Filter like "today", "overdue", "7 days", "no date"
      project_id:
        type: string
        description: Filter by project ID
      parent_id:
        type: string
        description: Filter by parent task ID (to get subtasks)
    rest:
      method: GET
      url: https://api.todoist.com/rest/v2/tasks
      query:
        filter: $PARAM_FILTER
        project_id: $PARAM_PROJECT_ID
        parent_id: $PARAM_PARENT_ID

  get_task:
    readonly: true
    description: Get a single task by ID. Use get_tasks(parent_id) for subtasks.
    params:
      id:
        type: string
        required: true
        description: Task ID
    rest:
      method: GET
      url: https://api.todoist.com/rest/v2/tasks/$PARAM_ID

  create_task:
    description: Create a new task (AI-created tasks get "AI" label)
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
    rest:
      method: POST
      url: https://api.todoist.com/rest/v2/tasks
      body:
        content: $PARAM_CONTENT
        due_string: $PARAM_DUE_STRING
        priority: $PARAM_PRIORITY
        project_id: $PARAM_PROJECT_ID
        description: $PARAM_DESCRIPTION
        parent_id: $PARAM_PARENT_ID
        labels: ["AI"]

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
    rest:
      method: POST
      url: https://api.todoist.com/rest/v2/tasks/$PARAM_ID
      body:
        content: $PARAM_CONTENT
        due_string: $PARAM_DUE_STRING
        priority: $PARAM_PRIORITY
        description: $PARAM_DESCRIPTION

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

  get_projects:
    readonly: true
    description: List all projects
    api:
      method: GET
      url: https://api.todoist.com/rest/v2/projects

  get_labels:
    description: List all labels
    api:
      method: GET
      url: https://api.todoist.com/rest/v2/labels
---

# Todoist

Personal task management - create, list, complete, update, delete tasks.

## Security

This plugin uses AgentOS secure REST executor. Credentials are never exposed to scripts - AgentOS injects them directly into API requests.

## Tools

### get_tasks
List tasks with optional filtering.

**Parameters:**
- `filter` (optional): Filter like "today", "overdue", "7 days"
- `project_id` (optional): Filter by project ID
- `parent_id` (optional): Filter by parent task ID (to get subtasks)

**Examples:**
```
use-plugin(plugin: "todoist", tool: "get_tasks")
use-plugin(plugin: "todoist", tool: "get_tasks", params: {filter: "today"})
use-plugin(plugin: "todoist", tool: "get_tasks", params: {filter: "overdue"})
use-plugin(plugin: "todoist", tool: "get_tasks", params: {parent_id: "123456"})  # Get subtasks
```

### get_task
Get a single task by ID.

**Parameters:**
- `id` (required): Task ID

**Example:**
```
use-plugin(plugin: "todoist", tool: "get_task", params: {id: "123456"})
```

**Getting subtasks:** Use `get_tasks(parent_id: "123456")` to fetch subtasks of a task.

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

### get_projects / get_labels
List all projects or labels.

**Examples:**
```
use-plugin(plugin: "todoist", tool: "get_projects")
use-plugin(plugin: "todoist", tool: "get_labels")
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
