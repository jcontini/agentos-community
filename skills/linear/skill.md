---
id: linear
name: Linear
description: Issue tracking and project management
category: productivity

icon: https://cdn.simpleicons.org/linear
color: "#5E6AD2"

abilities:
  - id: read_issues
    label: "Read issues and projects"
    endpoints:
      - "POST /graphql"  # GraphQL queries (read operations)
  - id: write_issues
    label: "Create and update issues"
    endpoints:
      - "POST /graphql"  # GraphQL mutations (write operations)
  - id: add_comments
    label: "Add comments"
    endpoints:
      - "POST /graphql"  # GraphQL mutations (comments)

auth:
  type: api_key
  header: Authorization
  prefix: ""
  help_url: https://linear.app/settings/api

api:
  base_url: https://api.linear.app
---

# Linear

**Use for:** Project management, issue tracking, sprint planning

## Quick Start

All requests go through the Passport proxy. Auth is automatic.

```bash
# Get your assigned issues
curl -s http://localhost:1111/cloud/linear/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ viewer { assignedIssues(first: 50) { nodes { identifier title state { name } } } } }"}' | jq .

# If you have multiple accounts:
curl -s http://localhost:1111/cloud/linear/graphql \
  -H "X-Passport-Account: work" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ viewer { assignedIssues(first: 50) { nodes { identifier title } } } }"}' | jq .
```

## API Reference

**Base URL:** `http://localhost:1111/cloud/linear`

Linear uses **GraphQL**. All queries go to `/graphql`.

### Common Queries

**Get all issues (with pagination):**
```graphql
{
  issues(first: 100) {
    nodes { id identifier title description state { name } }
    pageInfo { hasNextPage endCursor }
  }
}
```

**Get issue by identifier:**
```graphql
{
  issues(first: 1, filter: { identifier: { eq: "DEV-123" } }) {
    nodes { id identifier title description }
  }
}
```

**Get my assigned issues:**
```graphql
{
  viewer {
    assignedIssues(first: 50) {
      nodes { identifier title priority state { name } dueDate }
    }
  }
}
```

**Get teams:**
```graphql
{
  teams { nodes { id name } }
}
```

### Mutations

**Create issue:**
```graphql
mutation {
  issueCreate(input: {
    title: "Fix login bug"
    teamId: "TEAM-ID"
    description: "Users can't log in on mobile"
  }) {
    success
    issue { identifier url }
  }
}
```

**Update issue:**
```graphql
mutation {
  issueUpdate(id: "ISSUE-ID", input: {
    stateId: "STATE-ID"
    priority: 1
  }) {
    success
    issue { identifier state { name } }
  }
}
```

**Add comment:**
```graphql
mutation {
  commentCreate(input: {
    issueId: "ISSUE-ID"
    body: "Looking into this now"
  }) {
    success
  }
}
```

## Tips

- **Always paginate:** Default limit is 50. Use `first: 100` and check `hasNextPage`
- **Finding issues:** Query all issues and filter with jq, or use GraphQL filters
- **Issue identifiers:** Format is `TEAM-123` (e.g., `DEV-42`, `ENG-100`)

## Links

- [Linear GraphQL API](https://developers.linear.app/docs/graphql/working-with-the-graphql-api)
- [GraphQL Explorer](https://studio.apollographql.com/public/Linear-API/home)
