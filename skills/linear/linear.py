"""Linear — project management for engineering teams.

Replaces 16 GraphQL operations previously defined in skill.yaml.
All operations POST to the Linear GraphQL API with API key auth.
"""

import re
from agentos import surf

API_URL = "https://api.linear.app/graphql"


def _auth_header(params):
    key = params.get("auth", {}).get("key", "")
    return {"Authorization": key}


def _gql(params, query, variables=None):
    """Execute a GraphQL query against the Linear API."""
    headers = _auth_header(params)
    body = {"query": query}
    if variables:
        # Strip None values so Linear doesn't choke on null filters
        body["variables"] = {k: v for k, v in variables.items() if v is not None}
    with surf(profile="api") as client:
        resp = client.post(API_URL, json=body, headers=headers)
        resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise Exception(f"GraphQL error: {data['errors']}")
    return data["data"]


# ---------------------------------------------------------------------------
# Issue fields fragment (reused across queries)
# ---------------------------------------------------------------------------

_ISSUE_FIELDS = """
    id identifier title description
    state { id name type }
    priority url dueDate
    assignee { id name }
    project { id name }
    team { id key name }
    cycle { id number }
    parent { id identifier }
    labels { nodes { name } }
    createdAt updatedAt
"""

_ISSUE_FIELDS_FULL = _ISSUE_FIELDS + """
    children { nodes { id identifier title state { name } } }
    relations { nodes { id type relatedIssue { id identifier title } } }
    inverseRelations { nodes { id type issue { id identifier title } } }
"""


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def list_tasks(*, limit: int = 50, team_id: str = None, state_id: str = None, **params) -> list:
    """List issues with optional filters."""
    query = """
        query($limit: Int, $teamId: ID, $stateId: ID) {
          issues(
            first: $limit
            filter: {
              team: { id: { eq: $teamId } }
              state: { id: { eq: $stateId } }
            }
          ) {
            nodes { %s }
          }
        }
    """ % _ISSUE_FIELDS
    data = _gql(params, query, {"limit": limit, "teamId": team_id, "stateId": state_id})
    return data["issues"]["nodes"]


def get_task(*, id: str = None, url: str = None, **params) -> dict:
    """Get a single issue by ID or URL.

    If url is provided, extracts the identifier (e.g. PROJ-123) from the URL.
    """
    if url and not id:
        m = re.search(r"/issue/([A-Za-z0-9]+-\d+)", url)
        if m:
            id = m.group(1)
    if not id:
        raise ValueError("Either id or a valid Linear issue url is required")

    query = """
        query($id: String!) {
          issue(id: $id) { %s }
        }
    """ % _ISSUE_FIELDS_FULL
    data = _gql(params, query, {"id": id})
    return data["issue"]


def create_task(*, team_id: str, name: str, description: str = None,
                priority: int = None, project_id: str = None,
                parent_id: str = None, due: str = None, **params) -> dict:
    """Create a new issue."""
    query = """
        mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { %s }
          }
        }
    """ % _ISSUE_FIELDS
    input_vars = {"teamId": team_id, "title": name}
    if description is not None: input_vars["description"] = description
    if priority is not None: input_vars["priority"] = priority
    if project_id is not None: input_vars["projectId"] = project_id
    if parent_id is not None: input_vars["parentId"] = parent_id
    if due is not None: input_vars["dueDate"] = due
    data = _gql(params, query, {"input": input_vars})
    return data["issueCreate"]["issue"]


def update_task(*, id: str, name: str = None, description: str = None,
                priority: int = None, state_id: str = None,
                due: str = None, **params) -> dict:
    """Update an existing issue."""
    query = """
        mutation($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { %s }
          }
        }
    """ % _ISSUE_FIELDS
    input_vars = {}
    if name is not None: input_vars["title"] = name
    if description is not None: input_vars["description"] = description
    if priority is not None: input_vars["priority"] = priority
    if state_id is not None: input_vars["stateId"] = state_id
    if due is not None: input_vars["dueDate"] = due
    data = _gql(params, query, {"id": id, "input": input_vars})
    return data["issueUpdate"]["issue"]


def delete_task(*, id: str, **params) -> dict:
    """Delete an issue."""
    query = """
        mutation($id: String!) {
          issueDelete(id: $id) { success }
        }
    """
    data = _gql(params, query, {"id": id})
    return data["issueDelete"]


def list_projects(**params) -> list:
    """List all projects."""
    query = "{ projects { nodes { id name state } } }"
    data = _gql(params, query)
    return data["projects"]["nodes"]


def setup(**params) -> dict:
    """Auto-configure account params. Returns organization, teams, and viewer."""
    query = """
        {
          organization { urlKey name }
          teams { nodes { id key name } }
          viewer { id name email }
        }
    """
    data = _gql(params, query)
    return {
        "organization": data["organization"],
        "teams": data["teams"]["nodes"],
        "viewer": data["viewer"],
    }


def whoami(**params) -> dict:
    """Get current authenticated user."""
    query = "{ viewer { id name email } }"
    data = _gql(params, query)
    return data["viewer"]


def get_organization(**params) -> dict:
    """Get organization info including workspace URL slug."""
    query = "{ organization { id name urlKey } }"
    data = _gql(params, query)
    return data["organization"]


def get_teams(**params) -> list:
    """List all teams."""
    query = "{ teams { nodes { id key name } } }"
    data = _gql(params, query)
    return data["teams"]["nodes"]


def get_workflow_states(*, team_id: str, **params) -> list:
    """List workflow states for a team."""
    query = """
        query($teamId: ID!) {
          workflowStates(filter: { team: { id: { eq: $teamId } } }) {
            nodes { id name type position }
          }
        }
    """
    data = _gql(params, query, {"teamId": team_id})
    return data["workflowStates"]["nodes"]


def get_cycles(*, team_id: str, **params) -> list:
    """List cycles (sprints) for a team."""
    query = """
        query($teamId: String!) {
          team(id: $teamId) {
            cycles { nodes { id number startsAt endsAt } }
          }
        }
    """
    data = _gql(params, query, {"teamId": team_id})
    return data["team"]["cycles"]["nodes"]


def get_relations(*, id: str, **params) -> dict:
    """Get an issue's relationships (blocking, blocked by, related).

    Returns relation_id needed for remove_relation.
    """
    query = """
        query($id: String!) {
          issue(id: $id) {
            relations {
              nodes {
                id type
                relatedIssue { id identifier title }
              }
            }
            inverseRelations {
              nodes {
                id type
                issue { id identifier title }
              }
            }
          }
        }
    """
    data = _gql(params, query, {"id": id})
    issue = data["issue"]
    return {
        "blocks": issue["relations"]["nodes"],
        "blocked_by": issue["inverseRelations"]["nodes"],
    }


def add_blocker(*, id: str, blocker_id: str, **params) -> dict:
    """Add a blocking relationship (blocker_id blocks id)."""
    query = """
        mutation($input: IssueRelationCreateInput!) {
          issueRelationCreate(input: $input) {
            success
            issueRelation { id type }
          }
        }
    """
    data = _gql(params, query, {
        "input": {
            "issueId": blocker_id,
            "relatedIssueId": id,
            "type": "blocks",
        }
    })
    result = data["issueRelationCreate"]
    return {"success": result["success"], "id": result["issueRelation"]["id"]}


def remove_relation(*, relation_id: str, **params) -> dict:
    """Remove a relationship by its ID."""
    query = """
        mutation($id: String!) {
          issueRelationDelete(id: $id) { success }
        }
    """
    data = _gql(params, query, {"id": relation_id})
    return data["issueRelationDelete"]


def add_related(*, id: str, related_id: str, **params) -> dict:
    """Link two issues as related."""
    query = """
        mutation($input: IssueRelationCreateInput!) {
          issueRelationCreate(input: $input) {
            success
            issueRelation { id type }
          }
        }
    """
    data = _gql(params, query, {
        "input": {
            "issueId": id,
            "relatedIssueId": related_id,
            "type": "related",
        }
    })
    result = data["issueRelationCreate"]
    return {"success": result["success"], "id": result["issueRelation"]["id"]}
