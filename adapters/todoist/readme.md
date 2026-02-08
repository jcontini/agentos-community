---
id: todoist
name: Todoist
description: Personal task management
icon: icon.png
color: "#DE483A"

website: https://todoist.com
privacy_url: https://doist.com/privacy
terms_url: https://doist.com/terms-of-service

# API: Todoist Unified API v1 (https://developer.todoist.com/api/v1/)
# Note: REST API v2 and Sync API v9 are deprecated as of 2025

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
  outcome:
    terminology: Task
    relationships:
      includes:
        support: full
        mutation: move_task  # Update can't change project — route through move endpoint
      outcome_parent: full
      outcome_labels: full
    mapping:
      id: .id
      name: .content
      description: .description
      data.completed: .checked
      data.priority: 5 - .priority  # Invert: Todoist 4=urgent → AgentOS 1=highest
      target.date: .due.date?
      created_at: .added_at
      project_id:
        ref: journey
        value: .project_id
      _parent_id: .parent_id
      _labels:
        ref: tag
        value: .labels
        lookup: name

  journey:
    terminology: Project
    relationships:
      journey_parent: full
    mapping:
      id: .id
      name: .name
      data.color: .color
      _parent_id: .parent_id

  tag:
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
  outcome.list:
    description: List actionable outcomes (due today, overdue, or in inbox)
    returns: outcome[]
    web_url: https://app.todoist.com/app/today
    params:
      query: { type: string, default: "today | overdue | #Inbox", description: "Todoist filter query" }
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/tasks/filter
      query:
        query: .params.query
      response:
        root: /results

  outcome.list_all:
    description: List all outcomes with optional filters (no smart defaults)
    returns: outcome[]
    web_url: https://app.todoist.com/app/upcoming
    params:
      project_id: { type: string, description: "Filter by journey (project) ID" }
      section_id: { type: string, description: "Filter by section ID" }
      parent_id: { type: string, description: "Filter by parent outcome ID" }
      label: { type: string, description: "Filter by label name" }
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/tasks
      query:
        project_id: .params.project_id
        section_id: .params.section_id
        parent_id: .params.parent_id
        label: .params.label
      response:
        root: /results

  outcome.filter:
    description: Get outcomes matching a Todoist filter query
    returns: outcome[]
    web_url: https://app.todoist.com/app/today
    params:
      query: { type: string, required: true, description: "Todoist filter (e.g., 'today', 'overdue', '7 days')" }
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/tasks/filter
      query:
        query: .params.query
      response:
        root: /results

  outcome.get:
    description: Get a specific outcome by ID
    returns: outcome
    web_url: '"https://app.todoist.com/app/task/" + .params.id'
    params:
      id: { type: string, required: true, description: "Outcome ID" }
    rest:
      method: GET
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id'

  outcome.create:
    description: Create a new outcome
    returns: outcome
    params:
      name: { type: string, required: true, description: "Outcome name" }
      description: { type: string, description: "Outcome description" }
      due: { type: string, description: "Due date (natural language like 'tomorrow')" }
      priority: { type: integer, description: "Priority 1 (highest) to 4 (lowest)" }
      project_id: { type: string, description: "Journey (project) ID" }
      parent_id: { type: string, description: "Parent outcome ID (for sub-outcomes)" }
      labels: { type: array, description: "Label names" }
    rest:
      method: POST
      url: https://api.todoist.com/api/v1/tasks
      body:
        content: .params.name
        description: .params.description
        due_string: .params.due
        priority: 5 - .params.priority  # Invert: AgentOS 1=highest → Todoist 4=urgent
        project_id: .params.project_id
        parent_id: .params.parent_id
        labels: .params.labels

  outcome.update:
    description: Update an existing outcome (including moving to different journey)
    returns: outcome
    params:
      id: { type: string, required: true, description: "Outcome ID" }
      name: { type: string, description: "New name" }
      description: { type: string, description: "New description" }
      due: { type: string, description: "New due date" }
      priority: { type: integer, description: "New priority 1 (highest) to 4 (lowest)" }
      labels: { type: array, description: "New labels" }
      project_id: { type: string, description: "Move to different journey (project)" }
    rest:
      method: POST
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id'
      body:
        content: .params.name
        description: .params.description
        due_string: .params.due
        priority: 5 - .params.priority  # Invert: AgentOS 1=highest → Todoist 4=urgent
        labels: .params.labels

  outcome.complete:
    description: Mark an outcome as achieved
    returns: void
    params:
      id: { type: string, required: true, description: "Outcome ID" }
    rest:
      method: POST
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id + "/close"'

  outcome.reopen:
    description: Reopen an achieved outcome
    returns: void
    params:
      id: { type: string, required: true, description: "Outcome ID" }
    rest:
      method: POST
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id + "/reopen"'

  outcome.delete:
    description: Delete an outcome
    returns: void
    params:
      id: { type: string, required: true, description: "Outcome ID" }
    rest:
      method: DELETE
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id'

  journey.list:
    description: List all journeys (projects)
    returns: journey[]
    web_url: https://app.todoist.com/app/projects/active
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/projects
      response:
        root: /results

  tag.list:
    description: List all tags (labels)
    returns: tag[]
    web_url: https://app.todoist.com/app/labels
    rest:
      method: GET
      url: https://api.todoist.com/api/v1/labels
      response:
        root: /results

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
# Helper operations that return custom shapes (not entities).
# Have inline return schemas since there's no entity to reference.
# Naming convention: verb_noun

utilities:
  move_task:
    description: Move outcome to a different journey (project), section, or parent
    params:
      id: { type: string, required: true, description: "Outcome ID to move" }
      project_id: { type: string, description: "Target journey (project) ID" }
      section_id: { type: string, description: "Target section ID" }
      parent_id: { type: string, description: "Target parent outcome ID" }
    returns: outcome
    rest:
      method: POST
      url: '"https://api.todoist.com/api/v1/tasks/" + .params.id + "/move"'
      body:
        project_id: .params.project_id
        section_id: .params.section_id
        parent_id: .params.parent_id
---

# Todoist

Personal task management integration using [Todoist API v1](https://developer.todoist.com/api/v1/).

Todoist tasks map to **outcomes** and projects map to **journeys** in the AgentOS entity graph.

## Setup

1. Get your API token from https://todoist.com/app/settings/integrations/developer
2. Add credential in AgentOS Settings → Connectors → Todoist

## Features

- Full CRUD for outcomes (tasks)
- Journeys (projects) and tags (labels)
- Sub-outcomes via parent_id
- **Smart defaults**: `outcome.list` returns actionable outcomes (today, overdue, inbox)
- Rich filters via `query` param: `today`, `overdue`, `7 days`, `#ProjectName`, `@label`
- Move outcomes between journeys, sections, or parents
- `outcome.list_all` for raw list when you need everything

## Priority Scale

AgentOS uses a universal priority scale (1=highest, 4=lowest). This adapter maps to Todoist's inverted scale:

| AgentOS | Todoist | Client shows |
|---------|---------|--------------|
| 1 (highest) | 4 | P1 red flag |
| 2 | 3 | P2 orange |
| 3 | 2 | P3 blue |
| 4 (lowest) | 1 | P4 no flag |

## Technical Notes

- Uses Todoist Unified API v1 (REST v2 and Sync v9 are deprecated)
- Moving outcomes is handled via dedicated `/move` endpoint
- Include `project_id` in `outcome.update` to move — routed to move endpoint automatically
- Recurring due dates preserve the recurrence pattern
- `project_id` in the mapping creates an `includes` relationship (journey → outcome) via the ref system
