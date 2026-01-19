---
id: todoist
name: Todoist
description: Personal task management
icon: icon.png
color: "#E44332"
tags: [tasks, todos, reminders]

website: https://todoist.com
privacy_url: https://doist.com/privacy
terms_url: https://doist.com/terms-of-service

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: API Token
  help_url: https://todoist.com/help/articles/find-your-api-token-Jpzx9IIlB

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════
# Entity adapters transform API data into universal entity format.
# Mapping defined ONCE per entity — applied automatically to all operations.

adapters:
  task:
    terminology: Task
    relationships:
      task_project: full  # Adapter handles complexity (REST for read, Sync API for moves via move_task)
      task_parent: full
      task_labels: full
    mapping:
      id: .id
      title: .content
      description: .description
      completed: .is_completed
      priority: "5 - .priority"
      due_date: .due.date
      created_at: .created_at
      url: .url
      _project_id: .project_id
      _parent_id: .parent_id
      _labels: .labels

  project:
    terminology: Project
    relationships:
      project_parent: full
    mapping:
      id: .id
      name: .name
      color: .color
      is_favorite: .is_favorite
      _parent_id: .parent_id

  label:
    terminology: Label
    mapping:
      id: .id
      name: .name
      color: .color

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Entity operations that return typed entities.
# Mapping from `adapters` is applied automatically based on return type.
# Naming convention: {entity}.{operation}

operations:
  task.list:
    description: List tasks with optional filters
    returns: task[]
    params:
      filter: { type: string, description: "Todoist filter (e.g., 'today', 'overdue', '7 days')" }
      project_id: { type: string, description: "Filter by project ID" }
      section_id: { type: string, description: "Filter by section ID" }
      label: { type: string, description: "Filter by label name" }
    rest:
      method: GET
      url: https://api.todoist.com/rest/v2/tasks
      query:
        filter: "{{params.filter}}"
        project_id: "{{params.project_id}}"
        section_id: "{{params.section_id}}"
        label: "{{params.label}}"

  task.get:
    description: Get a specific task by ID
    returns: task
    params:
      id: { type: string, required: true, description: "Task ID" }
    rest:
      method: GET
      url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}"

  task.create:
    description: Create a new task
    returns: task
    params:
      title: { type: string, required: true, description: "Task title" }
      description: { type: string, description: "Task description" }
      due: { type: string, description: "Due date (natural language like 'tomorrow')" }
      priority: { type: integer, description: "Priority 1-4 (1=highest)" }
      project_id: { type: string, description: "Project ID" }
      parent_id: { type: string, description: "Parent task ID (for subtasks)" }
      labels: { type: array, description: "Label names" }
    rest:
      method: POST
      url: https://api.todoist.com/rest/v2/tasks
      body:
        content: "{{params.title}}"
        description: "{{params.description}}"
        due_string: "{{params.due}}"
        priority: "{{5 - params.priority}}"
        project_id: "{{params.project_id}}"
        parent_id: "{{params.parent_id}}"
        labels: "{{params.labels}}"

  task.update:
    description: Update an existing task
    returns: task
    params:
      id: { type: string, required: true, description: "Task ID" }
      title: { type: string, description: "New title" }
      description: { type: string, description: "New description" }
      due: { type: string, description: "New due date" }
      priority: { type: integer, description: "New priority" }
      labels: { type: array, description: "New labels" }
    rest:
      method: POST
      url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}"
      body:
        content: "{{params.title}}"
        description: "{{params.description}}"
        due_string: "{{params.due}}"
        priority: "{{5 - params.priority}}"
        labels: "{{params.labels}}"

  task.complete:
    description: Mark a task as complete
    returns: void
    params:
      id: { type: string, required: true, description: "Task ID" }
    rest:
      method: POST
      url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}/close"

  task.reopen:
    description: Reopen a completed task
    returns: void
    params:
      id: { type: string, required: true, description: "Task ID" }
    rest:
      method: POST
      url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}/reopen"

  task.delete:
    description: Delete a task
    returns: void
    params:
      id: { type: string, required: true, description: "Task ID" }
    rest:
      method: DELETE
      url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}"

  project.list:
    description: List all projects
    returns: project[]
    rest:
      method: GET
      url: https://api.todoist.com/rest/v2/projects

  label.list:
    description: List all labels
    returns: label[]
    rest:
      method: GET
      url: https://api.todoist.com/rest/v2/labels

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
# Helper operations that return custom shapes (not entities).
# Have inline return schemas since there's no entity to reference.
# Naming convention: verb_noun

utilities:
  move_task:
    description: Move task to a different project (REST API can't do this, uses Sync API)
    params:
      id: { type: string, required: true, description: "Task ID to move" }
      project_id: { type: string, required: true, description: "Target project ID" }
    returns:
      success: boolean
    rest:
      method: POST
      url: https://api.todoist.com/sync/v9/sync
      encoding: form
      body:
        commands: '[{"type":"item_move","uuid":"{{uuid}}","args":{"id":"{{params.id}}","project_id":"{{params.project_id}}"}}]'
      response:
        mapping:
          success: ".sync_status != null"
---

# Todoist

Personal task management integration.

## Setup

1. Get your API token from https://todoist.com/app/settings/integrations/developer
2. Add credential in AgentOS Settings → Connectors → Todoist

## Features

- Full CRUD for tasks
- Project and label support
- Subtasks via parent_id
- Rich filters: `today`, `overdue`, `7 days`, `no date`
- Move tasks between projects (via Sync API utility)

## Priority Mapping

Todoist uses inverted priorities (4=urgent, 1=normal). AgentOS normalizes this:
- Our priority 1 = Todoist priority 4 (urgent/red)
- Our priority 4 = Todoist priority 1 (normal)

## Limitations

- Moving tasks between projects requires the `move_task` utility (Sync API)
- Recurring task due dates must preserve the recurrence pattern
