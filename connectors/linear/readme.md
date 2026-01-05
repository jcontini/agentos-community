---
id: linear
name: Linear
description: Project management for engineering teams
icon: icon.png
color: "#5E6AD2"

website: https://linear.app
privacy_url: https://linear.app/privacy
terms_url: https://linear.app/terms

api:
  graphql_endpoint: "https://api.linear.app/graphql"

auth:
  type: api_key
  header: Authorization
  prefix: ""
  label: API Key
  help_url: https://linear.app/settings/api
  
  actions:
    whoami:
      description: Get current authenticated user
      graphql:
        query: "{ viewer { id name email } }"
        response:
          root: "data.viewer"
      returns:
        id: { type: string }
        name: { type: string }
        email: { type: string }

instructions: |
  Linear-specific notes:
  - Uses GraphQL API
  - Issues have human-readable IDs like "AGE-123" (stored in source_id)
  - Priority: 0=None, 1=Urgent, 2=High, 3=Medium, 4=Low
  - Creating issues requires a team_id (use get_teams first)
  - Workflow states vary by team
---

# Linear

Project management integration for engineering teams.

## Setup

1. Get your API key from https://linear.app/settings/api
2. Add credential in AgentOS Settings → Connectors → Linear

**Important**: Linear API keys are used WITHOUT the "Bearer" prefix.

## Features

- Full CRUD for issues (tasks)
- Projects and cycles
- Workflow states (customizable per team)
- Sub-issues via parent_id
- Issue relationships (blocking, related)

## Extended Operations

Some Linear-specific operations are available through extended actions:

- `get_teams` - List teams (needed for creating issues)
- `get_workflow_states` - List states for a team
- `get_cycles` - List cycles for a team
- `add_blocking` - Set blocking relationships
- `add_related` - Link related issues
