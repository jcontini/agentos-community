---
id: todoist
name: Todoist
description: Personal task management
color: "#DE483A"
website: "https://todoist.com"
privacy_url: "https://doist.com/privacy"
terms_url: "https://doist.com/terms-of-service"

connections:
  api:
    base_url: https://api.todoist.com/api/v1
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: API Token
    help_url: https://todoist.com/help/articles/find-your-api-token-Jpzx9IIlB

operations:
  list_tasks:
    web_url: https://app.todoist.com/app/today
  list_all_tasks:
    web_url: https://app.todoist.com/app/upcoming
  filter_task:
    web_url: https://app.todoist.com/app/today
  get_task:
    web_url: if (.params.url // "") != "" then .params.url else "https://app.todoist.com/app/task/" + .params.id end
  list_projects:
    web_url: https://app.todoist.com/app/projects/active
  list_tags:
    web_url: https://app.todoist.com/app/labels
---

# Todoist

Personal task management integration using [Todoist API v1](https://developer.todoist.com/api/v1/).

Todoist tasks map to **tasks** and projects map to **projects** on the AgentOS graph.

## Setup

1. Get your API token from https://todoist.com/app/settings/integrations/developer
2. Add credential in AgentOS Settings → Connectors → Todoist

## Features

- Full CRUD for tasks
- Projects and tags (labels)
- Sub-tasks via parent_id
- **Smart defaults**: `list_tasks` returns actionable tasks (today, overdue, inbox)
- Rich filters via `query` param: `today`, `overdue`, `7 days`, `#ProjectName`, `@label`
- Move tasks between projects, sections, or parents
- `list_all_tasks` for raw list when you need everything

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
- Moving tasks is handled via dedicated `/move` endpoint
- Include `project_id` in `update_task` to move — routed to move endpoint automatically
- Recurring due dates preserve the recurrence pattern
- `project_id` in the mapping creates an `includes` relationship (project → task) via the ref system
