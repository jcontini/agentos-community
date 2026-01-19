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

# Terminology: how Todoist names entities
terminology:
  task: Task
  project: Project
  label: Label

# Relationship support declarations
relationships:
  task_project:
    support: read_only  # Can read, but can't move tasks between projects via REST API
    field: project_id
  task_parent:
    support: full
    field: parent_id
  task_labels:
    support: full
    field: labels
  project_parent:
    support: full
    field: parent_id

instructions: |
  Todoist-specific notes:
  - Priority is inverted: 1=normal in API, 4=urgent in API
  - Projects cannot be changed after task creation (use Sync API to move)
  - Recurring tasks: preserve recurrence pattern when updating due dates

# Entity implementations
entities:
  task:
    list:
      label: "List tasks"
      params:
        filter: { type: string, description: "Todoist filter (e.g., 'today', 'overdue')" }
        project_id: { type: string, description: "Filter by project ID" }
      rest:
        method: GET
        url: https://api.todoist.com/rest/v2/tasks
        query:
          filter: "{{params.filter}}"
          project_id: "{{params.project_id}}"
        response:
          mapping:
            id: "[].id"
            title: "[].content"
            description: "[].description"
            completed: "[].is_completed"
            priority: "5 - [].priority"
            due_date: "[].due.date"
            project_id: "[].project_id"
            parent_id: "[].parent_id"
            labels: "[].labels"
            url: "[].url"

    get:
      label: "Get task"
      params:
        id: { type: string, required: true, description: "Task ID" }
      rest:
        method: GET
        url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}"
        response:
          mapping:
            id: ".id"
            title: ".content"
            description: ".description"
            completed: ".is_completed"
            priority: "5 - .priority"
            due_date: ".due.date"
            project_id: ".project_id"
            parent_id: ".parent_id"
            labels: ".labels"
            url: ".url"

    create:
      label: "Create task"
      params:
        title: { type: string, required: true, description: "Task title" }
        description: { type: string, description: "Task description" }
        due: { type: string, description: "Due date (natural language)" }
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
          priority: "{{params.priority | invert:5}}"
          project_id: "{{params.project_id}}"
          parent_id: "{{params.parent_id}}"
          labels: "{{params.labels}}"
        response:
          mapping:
            id: ".id"
            title: ".content"
            description: ".description"
            completed: "false"
            priority: "5 - .priority"
            due_date: ".due.date"
            project_id: ".project_id"
            labels: ".labels"
            url: ".url"

    update:
      label: "Update task"
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
          priority: "{{params.priority | invert:5}}"
          labels: "{{params.labels}}"
        response:
          mapping:
            id: ".id"
            title: ".content"
            description: ".description"
            completed: ".is_completed"
            priority: "5 - .priority"
            due_date: ".due.date"
            url: ".url"

    complete:
      label: "Complete task"
      params:
        id: { type: string, required: true, description: "Task ID" }
      rest:
        method: POST
        url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}/close"
        response:
          static:
            id: "{{params.id}}"
            completed: true

    reopen:
      label: "Reopen task"
      params:
        id: { type: string, required: true, description: "Task ID" }
      rest:
        method: POST
        url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}/reopen"
        response:
          static:
            id: "{{params.id}}"
            completed: false

    delete:
      label: "Delete task"
      params:
        id: { type: string, required: true, description: "Task ID" }
      rest:
        method: DELETE
        url: "https://api.todoist.com/rest/v2/tasks/{{params.id}}"
        response:
          static:
            success: true

  project:
    list:
      label: "List projects"
      rest:
        method: GET
        url: https://api.todoist.com/rest/v2/projects
        response:
          mapping:
            id: "[].id"
            name: "[].name"
            color: "[].color"
            parent_id: "[].parent_id"
            is_favorite: "[].is_favorite"

  label:
    list:
      label: "List labels"
      rest:
        method: GET
        url: https://api.todoist.com/rest/v2/labels
        response:
          mapping:
            id: "[].id"
            name: "[].name"
            color: "[].color"
---

# Todoist

Personal task management integration.

## Setup

1. Get your API token from https://todoist.com/app/settings/integrations/developer
2. Add credential in AgentOS Settings → Connectors → Todoist

## Features

- Full CRUD for tasks
- Project support
- Subtasks via parent_id
- Rich filters: `today`, `overdue`, `7 days`, `no date`
- Labels/tags

## Limitations

- Cannot move tasks between projects (must delete and recreate)
- Recurring task due dates must preserve the recurrence pattern
