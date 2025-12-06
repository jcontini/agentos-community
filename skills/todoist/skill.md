---
id: todoist
name: Todoist
description: Personal task management
category: productivity

icon: https://cdn.simpleicons.org/todoist
color: "#e44332"

abilities:
  - id: read_tasks
    label: "Read your tasks"
    endpoints:
      - "GET /rest/v2/tasks"
      - "GET /rest/v2/tasks/*"
      - "GET /rest/v2/projects"
      - "GET /rest/v2/projects/*"
      - "GET /rest/v2/labels"
      - "GET /rest/v2/labels/*"
  - id: write_tasks
    label: "Create and modify tasks"
    endpoints:
      - "POST /rest/v2/tasks"
      - "POST /rest/v2/tasks/*"
      - "POST /rest/v2/tasks/*/close"
      - "POST /rest/v2/tasks/*/reopen"
  - id: delete_tasks
    label: "Delete tasks"
    destructive: true
    endpoints:
      - "DELETE /rest/v2/tasks/*"
  - id: manage_projects
    label: "Manage projects"
    endpoints:
      - "POST /rest/v2/projects"
      - "POST /rest/v2/projects/*"
      - "DELETE /rest/v2/projects/*"

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  help_url: https://todoist.com/help/articles/find-your-api-token-Jpzx9IIlB

api:
  base_url: https://api.todoist.com
---

# Todoist

**Use for:** Task management - create, list, complete, update, delete tasks and projects

## Quick Start

All requests go through the Passport proxy. Auth is automatic.

```bash
# List all tasks
curl -s http://localhost:1111/cloud/todoist/rest/v2/tasks | jq .

# If you have multiple accounts, specify which one:
curl -s http://localhost:1111/cloud/todoist/rest/v2/tasks \
  -H "X-Passport-Account: work"
```

## API Reference

**Base URL:** `http://localhost:1111/cloud/todoist`

The proxy mirrors the Todoist REST API v2. Paths are identical to `https://api.todoist.com/...`

## Common Operations

### Tasks

**List all tasks:**
```bash
curl -s http://localhost:1111/cloud/todoist/rest/v2/tasks | jq .
```

**Get tasks due today:**
```bash
curl -s "http://localhost:1111/cloud/todoist/rest/v2/tasks?filter=today" | jq .
```

**Get tasks due this week:**
```bash
curl -s "http://localhost:1111/cloud/todoist/rest/v2/tasks?filter=7%20days" | jq .
```

**Get task by ID (with subtasks):**
```bash
TASK_ID="123456789"
curl -s "http://localhost:1111/cloud/todoist/rest/v2/tasks/$TASK_ID" | jq .
# Get subtasks
curl -s "http://localhost:1111/cloud/todoist/rest/v2/tasks?parent_id=$TASK_ID" | jq .
```

**Create a task:**
```bash
curl -s -X POST http://localhost:1111/cloud/todoist/rest/v2/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Task content here",
    "due_string": "today",
    "labels": ["AI"]
  }' | jq .
```

**Create task in specific project:**
```bash
curl -s -X POST http://localhost:1111/cloud/todoist/rest/v2/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Task content",
    "project_id": "PROJECT_ID_HERE",
    "due_string": "tomorrow",
    "priority": 4,
    "labels": ["AI"]
  }' | jq .
```

**Update a task:**
```bash
TASK_ID="123456789"
curl -s -X POST "http://localhost:1111/cloud/todoist/rest/v2/tasks/$TASK_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Updated content",
    "due_string": "next week"
  }' | jq .
```

**Complete a task:**
```bash
TASK_ID="123456789"
curl -s -X POST "http://localhost:1111/cloud/todoist/rest/v2/tasks/$TASK_ID/close"
```

**Reopen a task:**
```bash
TASK_ID="123456789"
curl -s -X POST "http://localhost:1111/cloud/todoist/rest/v2/tasks/$TASK_ID/reopen"
```

**Delete a task:**
```bash
TASK_ID="123456789"
curl -s -X DELETE "http://localhost:1111/cloud/todoist/rest/v2/tasks/$TASK_ID"
```

### Projects

**List all projects:**
```bash
curl -s http://localhost:1111/cloud/todoist/rest/v2/projects | jq .
```

**Get tasks in a project:**
```bash
PROJECT_ID="123456789"
curl -s "http://localhost:1111/cloud/todoist/rest/v2/tasks?project_id=$PROJECT_ID" | jq .
```

**Create a project:**
```bash
curl -s -X POST http://localhost:1111/cloud/todoist/rest/v2/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "New Project"}' | jq .
```

### Labels

**List all labels:**
```bash
curl -s http://localhost:1111/cloud/todoist/rest/v2/labels | jq .
```

## AI Task Defaults

When creating tasks on behalf of the user:
1. **Default due date:** If user doesn't specify, use `"due_string": "today"`
2. **AI label:** Always include `"labels": ["AI"]` so user knows the task was AI-created
3. **Project:** If user specifies a project, include `project_id` at creation (cannot be changed later)

## Important Notes

- **Subtasks:** Always check for subtasks using `?parent_id=TASK_ID` when retrieving a task
- **Moving tasks:** Cannot update `project_id` after creation. Must delete and recreate.
- **Priority:** 1 (normal) to 4 (urgent)
- **Due dates:** Supports natural language (`today`, `tomorrow`, `next monday`) or ISO format (`2025-01-15`)
- **Rate limits:** ~450 requests per 15 minutes. Check `X-RateLimit-*` headers.

## Error Handling

Passport translates errors to user-friendly messages. Common issues:
- `needs_reauth`: Tell user to reconnect Todoist in Passport settings
- Rate limited: Wait and retry (check `retry_after` in response)

For full Todoist API docs: https://developer.todoist.com/rest/v2/
