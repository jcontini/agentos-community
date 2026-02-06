---
id: linear
name: Linear
description: Project management for engineering teams
icon: icon.png
color: "#636FD3"

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
  
  # Account-level params for auto-injection
  # These are configured per-account and injected into operations automatically
  # AI should call `setup` utility after credential is added to auto-configure these
  account_params:
    workspace_slug:
      type: string
      required: false
      label: "Workspace URL"
      description: "Organization URL slug for web links (e.g., 'thirdparty' in linear.app/thirdparty/...)"
      discover: get_organization  # Returns urlKey field
    team_id:
      type: string
      required: false
      label: "Default Team"
      description: "Filter operations to this team by default"
      discover: get_teams  # Returns team id and key

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════
# Entity adapters transform API data into universal entity format.
# Mapping defined ONCE per entity — applied automatically to all operations.

adapters:
  task:
    terminology: Issue
    relationships:
      task_project: full
      task_parent: full
      task_labels: read_only
    mapping:
      id: .id
      remote_id: .identifier
      title: .title
      description: .description
      completed: '.state.type == "completed"'
      status: 'if .state.type == "completed" then "done" elif .state.type == "canceled" then "cancelled" elif .state.type == "started" then "in_progress" else "open" end'
      priority: .priority
      due_date: .dueDate
      url: .url
      created_at: .createdAt
      updated_at: .updatedAt
      
      # Assignee display fields (denormalized for views)
      # Note: assignee, cycle, parent can be null — use (.x // {}).field for null safety
      assignee.id: '(.assignee // {}).id'
      assignee.name: '(.assignee // {}).name'
      
      # Typed reference: creates person entity + assigned_to relationship
      assigned_to:
        person:
          id: '(.assignee // {}).id'
          name: '(.assignee // {}).name'
      project_id: '(.project // {}).id'
      _project_name: '(.project // {}).name'
      _team_id: '(.team // {}).id'
      _team_name: '(.team // {}).name'
      _cycle_id: '(.cycle // {}).id'
      _cycle_number: '(.cycle // {}).number'
      _state_id: '(.state // {}).id'
      _state_name: '(.state // {}).name'
      _state_type: '(.state // {}).type'
      _parent_id: '(.parent // {}).id'
      _labels: '[((.labels // {}).nodes // [])[] | .name]'
      _children: '[((.children // {}).nodes // [])[] | .id]'
      blocked_by: '[((.inverseRelations // {}).nodes // [])[] | .issue.id]'
      blocks: '[((.relations // {}).nodes // [])[] | .relatedIssue.id]'

  project:
    terminology: Project
    mapping:
      id: .id
      name: .name
      state: .state

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Entity operations that return typed entities.
# Mapping from `adapters` is applied automatically based on return type.
# Naming convention: {entity}.{operation}

operations:
  task.list:
    description: List issues with optional filters
    returns: task[]
    web_url: '"https://linear.app/" + .params.workspace_slug'
    params:
      limit: { type: integer, default: 50, description: "Max issues to return" }
      team_id: { type: string, description: "Filter by team ID" }
      state_id: { type: string, description: "Filter by workflow state ID" }
    graphql:
      query: |
        query($limit: Int, $teamId: ID, $stateId: ID) {
          issues(
            first: $limit
            filter: {
              team: { id: { eq: $teamId } }
              state: { id: { eq: $stateId } }
            }
          ) {
            nodes {
              id identifier title description
              state { id name type }
              priority
              dueDate
              assignee { id name }
              project { id name }
              team { id key name }
              cycle { id number }
              parent { id identifier }
              labels { nodes { name } }
              url
              createdAt updatedAt
            }
          }
        }
      variables:
        limit: .params.limit
        teamId: .params.team_id
        stateId: .params.state_id
      response:
        root: /data/issues/nodes

  task.get:
    description: Get a specific issue by ID
    returns: task
    params:
      id: { type: string, required: true, description: "Issue ID" }
    graphql:
      query: |
        query($id: String!) {
          issue(id: $id) {
            id identifier title description
            state { id name type }
            priority url dueDate
            assignee { id name }
            project { id name }
            team { id key name }
            cycle { id number }
            parent { id identifier }
            children { nodes { id identifier title state { name } } }
            labels { nodes { name } }
            relations { nodes { type relatedIssue { id identifier } } }
            inverseRelations { nodes { type issue { id identifier } } }
            createdAt updatedAt
          }
        }
      variables:
        id: .params.id
      response:
        root: /data/issue

  task.create:
    description: Create a new issue
    returns: task
    params:
      team_id: { type: string, required: true, description: "Team ID (use get_teams to find)" }
      title: { type: string, required: true, description: "Issue title" }
      description: { type: string, description: "Issue description (markdown)" }
      priority: { type: integer, description: "Priority 0-4 (0=none, 1=urgent, 4=low)" }
      project_id: { type: string, description: "Project ID" }
      parent_id: { type: string, description: "Parent issue ID (for sub-issues)" }
      due: { type: string, description: "Due date (ISO format)" }
    graphql:
      query: |
        mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue {
              id identifier title url
              state { id name type }
              project { id name }
              team { id key name }
              assignee { id name }
              priority dueDate
              createdAt updatedAt
            }
          }
        }
      variables:
        input:
          teamId: .params.team_id
          title: .params.title
          description: .params.description
          priority: .params.priority
          projectId: .params.project_id
          parentId: .params.parent_id
          dueDate: .params.due
      response:
        root: /data/issueCreate/issue

  task.update:
    description: Update an existing issue
    returns: task
    params:
      id: { type: string, required: true, description: "Issue ID" }
      title: { type: string, description: "New title" }
      description: { type: string, description: "New description" }
      priority: { type: integer, description: "New priority 0-4" }
      state_id: { type: string, description: "New workflow state ID" }
      due: { type: string, description: "New due date" }
    graphql:
      query: |
        mutation($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue {
              id identifier title url
              state { id name type }
              project { id name }
              team { id key name }
              assignee { id name }
              priority dueDate
              createdAt updatedAt
            }
          }
        }
      variables:
        id: .params.id
        input:
          title: .params.title
          description: .params.description
          priority: .params.priority
          stateId: .params.state_id
          dueDate: .params.due
      response:
        root: /data/issueUpdate/issue

  task.delete:
    description: Delete an issue
    returns: void
    params:
      id: { type: string, required: true, description: "Issue ID" }
    graphql:
      query: |
        mutation($id: String!) {
          issueDelete(id: $id) { success }
        }
      variables:
        id: .params.id

  project.list:
    description: List all projects
    returns: project[]
    web_url: '"https://linear.app/" + .params.workspace_slug + "/projects"'
    graphql:
      query: "{ projects { nodes { id name state } } }"
      response:
        root: /data/projects/nodes

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
# Helper operations that return custom shapes (not entities).
# Naming convention: verb_noun

utilities:
  setup:
    description: |
      Auto-configure account params. Call this after adding a Linear credential.
      Returns organization info (for workspace_slug) and teams (for team_id).
      - If one team: set both workspace_slug and team_id automatically
      - If multiple teams: set workspace_slug, ask user which team to use as default
      After getting response, set params via PUT /api/settings/account_params
    returns:
      organization.urlKey: string
      organization.name: string
      teams: array
      viewer.id: string
      viewer.name: string
      viewer.email: string
    graphql:
      query: |
        {
          organization { urlKey name }
          teams { nodes { id key name } }
          viewer { id name email }
        }
      response:
        root: /data

  whoami:
    description: Get current authenticated user (for credential verification)
    returns:
      id: string
      name: string
      email: string
    graphql:
      query: "{ viewer { id name email } }"
      response:
        root: /data/viewer

  get_organization:
    description: Get organization info including workspace URL slug
    returns:
      id: string
      name: string
      urlKey: string
    graphql:
      query: "{ organization { id name urlKey } }"
      response:
        root: /data/organization

  get_teams:
    description: List all teams (needed to create issues)
    returns:
      id: string
      key: string
      name: string
    graphql:
      query: "{ teams { nodes { id key name } } }"
      response:
        root: /data/teams/nodes

  get_workflow_states:
    description: List workflow states for a team
    params:
      team_id: { type: string, required: true, description: "Team ID" }
    returns:
      id: string
      name: string
      type: string
      position: number
    graphql:
      query: |
        query($teamId: ID!) {
          workflowStates(filter: { team: { id: { eq: $teamId } } }) {
            nodes { id name type position }
          }
        }
      variables:
        teamId: .params.team_id
      response:
        root: /data/workflowStates/nodes

  get_cycles:
    description: List cycles (sprints) for a team
    params:
      team_id: { type: string, required: true, description: "Team ID" }
    returns:
      id: string
      number: integer
      startsAt: datetime
      endsAt: datetime
    graphql:
      query: |
        query($teamId: String!) {
          team(id: $teamId) {
            cycles { nodes { id number startsAt endsAt } }
          }
        }
      variables:
        teamId: .params.team_id
      response:
        root: /data/team/cycles/nodes

  get_relations:
    description: Get an issue's relationships (blocking, blocked by, related). Returns relation_id needed for remove_relation.
    params:
      id: { type: string, required: true, description: "Issue ID" }
    returns:
      blocks: array
      blocked_by: array
      related: array
    graphql:
      query: |
        query($id: String!) {
          issue(id: $id) {
            relations {
              nodes {
                id
                type
                relatedIssue { id identifier title }
              }
            }
            inverseRelations {
              nodes {
                id
                type
                issue { id identifier title }
              }
            }
          }
        }
      variables:
        id: .params.id
      response:
        root: /data/issue
        mapping:
          blocks: .relations.nodes
          blocked_by: .inverseRelations.nodes

  add_blocker:
    description: Add a blocking relationship (blocker_id blocks id). Returns relation ID in `id` field.
    params:
      id: { type: string, required: true, description: "Issue being blocked" }
      blocker_id: { type: string, required: true, description: "Issue that is blocking" }
    returns: operation_result
    graphql:
      query: |
        mutation($input: IssueRelationCreateInput!) {
          issueRelationCreate(input: $input) {
            success
            issueRelation { id type }
          }
        }
      variables:
        input:
          issueId: .params.blocker_id
          relatedIssueId: .params.id
          type: '"blocks"'
      response:
        root: /data/issueRelationCreate
        mapping:
          success: .success
          id: .issueRelation.id

  remove_relation:
    description: Remove a relationship by its ID (get ID from add_blocker/add_related response or issue query)
    params:
      relation_id: { type: string, required: true, description: "Relation ID to delete" }
    returns: operation_result
    graphql:
      query: |
        mutation($id: String!) {
          issueRelationDelete(id: $id) {
            success
          }
        }
      variables:
        id: .params.relation_id
      response:
        root: /data/issueRelationDelete
        mapping:
          success: .success

  add_related:
    description: Link two issues as related. Returns relation ID in `id` field.
    params:
      id: { type: string, required: true, description: "First issue ID" }
      related_id: { type: string, required: true, description: "Second issue ID" }
    returns: operation_result
    graphql:
      query: |
        mutation($input: IssueRelationCreateInput!) {
          issueRelationCreate(input: $input) {
            success
            issueRelation { id type }
          }
        }
      variables:
        input:
          issueId: .params.id
          relatedIssueId: .params.related_id
          type: '"related"'
      response:
        root: /data/issueRelationCreate
        mapping:
          success: .success
          id: .issueRelation.id


instructions: |
  Linear plugin notes for AI:
  
  **SETUP (do this after credential is added):**
  1. Call `setup` utility — returns organization, teams, and user info
  2. Extract workspace_slug from organization.urlKey
  3. If one team: use its id as team_id
     If multiple teams: ask user "Which Linear team should be your default?"
  4. Set params via PUT /api/settings/account_params:
     ```
     PUT /api/settings/account_params
     {"value": {"linear:AccountName": {"workspace_slug": "urlKey", "team_id": "team-id"}}}
     ```
  
  Creating issues:
  - Requires team_id — if not set in account params, call get_teams first
  
  Completing/reopening issues:
  1. Get the issue's team_id (from task.get or task.list)
  2. Call get_workflow_states with team_id
  3. Find state with type "completed" (for complete) or "backlog" (for reopen)
  4. Call task.update with state_id
  
  Managing relationships:
  - add_blocker/add_related return operation_result with relation ID in `id` field
  - get_relations returns all relationships with their IDs
  - remove_relation takes relation_id param, returns operation_result
  
  Other notes:
  - Issues have human-readable IDs like "AGE-123" (in remote_id field)
  - Priority: 0=None, 1=Urgent, 2=High, 3=Medium, 4=Low
  - Web URLs: https://linear.app/{workspace_slug}/issue/{identifier}
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

## Workflow

Linear uses customizable workflow states per team. Common patterns:

| State Type | Typical Names | Maps to |
|------------|---------------|---------|
| backlog | Backlog, Triage | open |
| unstarted | Todo | open |
| started | In Progress, In Review | in_progress |
| completed | Done | done |
| canceled | Canceled | cancelled |

To change an issue's state, use `task.update` with `state_id` from `get_workflow_states`.

## Priority Scale

| Value | Meaning |
|-------|---------|
| 0 | No priority |
| 1 | Urgent |
| 2 | High |
| 3 | Medium |
| 4 | Low |

## Completing Issues

To mark an issue complete:
1. Call `get_workflow_states` with the issue's team_id
2. Find the state with `type: "completed"`
3. Call `complete_task` with the issue id and state_id

Or use `task.update` directly with `state_id`.
