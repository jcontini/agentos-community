---
id: todoist
name: Todoist
description: Personal task management
icon: icon.png
color: "#E44332"

website: https://todoist.com
privacy_url: https://doist.com/privacy
terms_url: https://doist.com/terms-of-service

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: API Token
  help_url: https://todoist.com/help/articles/find-your-api-token-Jpzx9IIlB

instructions: |
  Todoist-specific notes:
  - Priority is inverted: 1=normal in API, 4=urgent in API
  - Projects cannot be changed after task creation
  - Recurring tasks: preserve recurrence pattern when updating due dates
  - AI-created tasks automatically get the "AI" label
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
