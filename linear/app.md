---
id: linear
name: Linear
description: Project management with blocking relationships, cycles, and full API access
icon: https://cdn.simpleicons.org/linear
color: "#5E6AD2"

website: https://linear.app
privacy_url: https://linear.app/privacy
terms_url: https://linear.app/terms

tags: [issues, tickets, project management]

auth:
  type: api_key
  header: Authorization
  prefix: ""
  help_url: https://linear.app/settings/api

api:
  base_url: https://api.linear.app/graphql
  type: graphql

actions:
  # =============================================================================
  # READ OPERATIONS (No IDs needed)
  # =============================================================================
  
  whoami:
    readonly: true
    description: Get current authenticated user info
    graphql:
      query: "{ viewer { id name email } }"
      extract: .data.viewer

  get_teams:
    readonly: true
    description: List all teams (use to get team IDs for other operations)
    graphql:
      query: "{ teams { nodes { id key name } } }"
      extract: .data.teams.nodes

  get_projects:
    readonly: true
    description: List all projects
    graphql:
      query: "{ projects { nodes { id name state priority lead { name } } } }"
      extract: .data.projects.nodes

  get_workflow_states:
    readonly: true
    description: List workflow states for a team (use to get state IDs)
    params:
      team_id:
        type: string
        required: true
        description: Team ID (get from get_teams)
    graphql:
      query: |
        query($teamId: ID!) {
          workflowStates(filter: { team: { id: { eq: $teamId } } }) {
            nodes { id name type position }
          }
        }
      variables:
        teamId: $PARAM_TEAM_ID
      extract: .data.workflowStates.nodes

  get_cycles:
    readonly: true
    description: List cycles for a team
    params:
      team_id:
        type: string
        required: true
        description: Team ID (get from get_teams)
    graphql:
      query: |
        query($teamId: ID!) {
          team(id: $teamId) {
            cycles { nodes { id number startsAt endsAt } }
          }
        }
      variables:
        teamId: $PARAM_TEAM_ID
      extract: .data.team.cycles.nodes

  # =============================================================================
  # ISSUES - LIST & GET
  # =============================================================================

  get_issues:
    readonly: true
    description: List issues, optionally filtered by team/state/assignee
    params:
      team_id:
        type: string
        description: Filter by team ID
      state_id:
        type: string
        description: Filter by state ID
      assignee_id:
        type: string
        description: Filter by assignee ID (use "me" for current user)
      limit:
        type: number
        description: Max results (default 50)
    graphql:
      query: |
        query($teamId: ID, $stateId: ID, $assigneeId: ID, $limit: Int) {
          issues(
            first: $limit
            filter: {
              team: { id: { eq: $teamId } }
              state: { id: { eq: $stateId } }
              assignee: { id: { eq: $assigneeId } }
            }
          ) {
            nodes {
              id identifier title
              state { id name }
              priority
              assignee { id name }
              cycle { number }
              project { name }
            }
          }
        }
      variables:
        teamId: $PARAM_TEAM_ID
        stateId: $PARAM_STATE_ID
        assigneeId: $PARAM_ASSIGNEE_ID
        limit: $PARAM_LIMIT
      extract: .data.issues.nodes

  get_issue:
    readonly: true
    description: Get full issue details including relations
    params:
      id:
        type: string
        required: true
        description: Issue identifier (e.g., "AGE-8") or UUID
    graphql:
      query: |
        query($id: String!) {
          issue(id: $id) {
            id identifier title description
            state { id name }
            priority url
            assignee { id name }
            cycle { id number }
            project { id name }
            team { id key name }
            parent { id identifier title }
            children { nodes { id identifier title state { name } } }
            relations { nodes { id type relatedIssue { identifier title } } }
            inverseRelations { nodes { id type issue { identifier title } } }
          }
        }
      variables:
        id: $PARAM_ID
      extract: .data.issue

  # =============================================================================
  # ISSUES - CREATE & UPDATE
  # =============================================================================

  create_issue:
    description: Create a new issue
    params:
      team_id:
        type: string
        required: true
        description: Team ID (get from get_teams)
      title:
        type: string
        required: true
        description: Issue title
      description:
        type: string
        description: Issue description (markdown supported)
      priority:
        type: number
        description: Priority 0-4 (1=Urgent, 2=High, 3=Medium, 4=Low)
      state_id:
        type: string
        description: State ID (get from get_workflow_states)
      project_id:
        type: string
        description: Project ID (get from get_projects)
      cycle_id:
        type: string
        description: Cycle ID (get from get_cycles)
      assignee_id:
        type: string
        description: Assignee user ID
      parent_id:
        type: string
        description: Parent issue ID to create as sub-issue
    graphql:
      query: |
        mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id identifier title url parent { identifier } }
          }
        }
      variables:
        input:
          teamId: $PARAM_TEAM_ID
          title: $PARAM_TITLE
          description: $PARAM_DESCRIPTION
          priority: $PARAM_PRIORITY
          stateId: $PARAM_STATE_ID
          projectId: $PARAM_PROJECT_ID
          cycleId: $PARAM_CYCLE_ID
          assigneeId: $PARAM_ASSIGNEE_ID
          parentId: $PARAM_PARENT_ID
      extract: .data.issueCreate

  update_issue:
    description: Update an existing issue
    params:
      id:
        type: string
        required: true
        description: Issue ID or identifier (e.g., "AGE-8")
      title:
        type: string
        description: New title
      description:
        type: string
        description: New description (markdown)
      priority:
        type: number
        description: New priority 0-4
      state_id:
        type: string
        description: New state ID (get from get_workflow_states)
      project_id:
        type: string
        description: Project ID (get from get_projects)
      cycle_id:
        type: string
        description: Cycle ID (get from get_cycles, null to remove)
      assignee_id:
        type: string
        description: New assignee user ID
      parent_id:
        type: string
        description: Parent issue ID (set to make this a sub-issue)
    graphql:
      query: |
        mutation($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { id identifier title state { name } project { name } parent { identifier } url }
          }
        }
      variables:
        id: $PARAM_ID
        input:
          title: $PARAM_TITLE
          description: $PARAM_DESCRIPTION
          priority: $PARAM_PRIORITY
          stateId: $PARAM_STATE_ID
          projectId: $PARAM_PROJECT_ID
          cycleId: $PARAM_CYCLE_ID
          assigneeId: $PARAM_ASSIGNEE_ID
          parentId: $PARAM_PARENT_ID
      extract: .data.issueUpdate

  delete_issue:
    description: Permanently delete an issue
    params:
      id:
        type: string
        required: true
        description: Issue ID or identifier (e.g., "DEV-123")
    graphql:
      query: |
        mutation($id: String!) {
          issueDelete(id: $id) {
            success
          }
        }
      variables:
        id: $PARAM_ID
      extract: .data.issueDelete

  # =============================================================================
  # ISSUE RELATIONSHIPS
  # =============================================================================

  add_related:
    description: Mark two issues as related to each other
    params:
      issue_id:
        type: string
        required: true
        description: UUID of the first issue
      related_issue_id:
        type: string
        required: true
        description: UUID of the related issue
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
          issueId: $PARAM_ISSUE_ID
          relatedIssueId: $PARAM_RELATED_ISSUE_ID
          type: related
      extract: .data.issueRelationCreate

  add_blocking:
    description: Set issue A blocks issue B (A must complete before B can start)
    params:
      blocker_id:
        type: string
        required: true
        description: ID of issue that blocks (the prerequisite)
      blocked_id:
        type: string
        required: true
        description: ID of issue that is blocked (the dependent)
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
          issueId: $PARAM_BLOCKER_ID
          relatedIssueId: $PARAM_BLOCKED_ID
          type: blocks
      extract: .data.issueRelationCreate

  remove_relation:
    description: Remove a relation between issues
    params:
      relation_id:
        type: string
        required: true
        description: Relation ID (get from get_issue relations)
    graphql:
      query: |
        mutation($id: String!) {
          issueRelationDelete(id: $id) { success }
        }
      variables:
        id: $PARAM_RELATION_ID
      extract: .data.issueRelationDelete

---

# Linear

Full-featured Linear integration with blocking relationships, cycles, and full GraphQL API access.

## Design Philosophy

This plugin exposes Linear's GraphQL API directly. Operations that need IDs (like creating issues) require you to fetch those IDs first using list operations. This is intentional:

- **Explicit over implicit** - No hidden API calls
- **AI-friendly** - The AI sees the full workflow
- **Composable** - Each action does one thing well

## Authentication

Get your API key from: https://linear.app/settings/api

**Important**: Linear personal API keys are used WITHOUT the "Bearer" prefix.

## Common Workflows

### Create an issue

1. `get_teams` → Get team ID
2. `get_workflow_states(team_id: "...")` → Get state ID (optional)
3. `create_issue(team_id: "...", title: "...", state_id: "...")`

### Update issue state

1. `get_issue(id: "AGE-8")` → Get current issue and team ID
2. `get_workflow_states(team_id: "...")` → Find the desired state ID
3. `update_issue(id: "AGE-8", state_id: "...")`

### Link related issues

1. `get_issue(id: "AGE-8")` → Get issue UUID
2. `get_issue(id: "AGE-6")` → Get other issue UUID  
3. `add_related(issue_id: "...", related_issue_id: "...")`

### Set up blocking relationship

1. `get_issue(id: "AGE-8")` → Get issue UUID
2. `get_issue(id: "AGE-6")` → Get other issue UUID  
3. `add_blocking(blocker_id: "...", blocked_id: "...")`

## Tools Reference

### Read Operations

| Tool | Purpose | Returns |
|------|---------|---------|
| `whoami` | Current user info | id, name, email |
| `get_teams` | All teams | id, key, name |
| `get_projects` | All projects | id, name, state, priority |
| `get_workflow_states(team_id)` | Team's workflow states | id, name, type |
| `get_cycles(team_id)` | Team's cycles | id, number, dates |
| `get_issues(...)` | Issues with filters | id, identifier, title, state, etc |
| `get_issue(id)` | Full issue details | Everything including relations |

### Write Operations

| Tool | Purpose | Required Params |
|------|---------|-----------------|
| `create_issue` | Create new issue | team_id, title |
| `update_issue` | Update issue | id |
| `delete_issue` | Permanently delete issue | id |
| `add_related` | Mark two issues as related | issue_id, related_issue_id |
| `add_blocking` | A blocks B | blocker_id, blocked_id |
| `remove_relation` | Remove relation | relation_id |

## Priority Values

| Value | Meaning |
|-------|---------|
| 0 | No priority |
| 1 | Urgent |
| 2 | High |
| 3 | Medium |
| 4 | Low |

## Workflow State Types

| Type | Meaning |
|------|---------|
| backlog | Not started, low priority |
| unstarted | Ready to start |
| started | In progress |
| completed | Done |
| canceled | Won't do |
