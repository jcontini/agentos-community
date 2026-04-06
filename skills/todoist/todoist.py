import re
from agentos import http, connection, provides, returns, web_read

API_BASE = "https://api.todoist.com/api/v1"


def _auth_header(params):
    key = params.get("auth", {}).get("key", "")
    return {"Authorization": f"Bearer {key}"}


def _map_task(t: dict) -> dict:
    priority_raw = t.get("priority", 1)
    due = t.get("due") or {}
    return {
        "id": t.get("id"),
        "name": t.get("content"),
        "content": t.get("description"),
        "priority": 5 - priority_raw,
        "target": {"date": due.get("date")} if due.get("date") else None,
        "published": t.get("added_at"),
        "projectId": t.get("project_id"),
        "parentId": t.get("parent_id"),
        "labels": t.get("labels", []),
        "url": t.get("url"),
    }


def _map_project(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "color": p.get("color"),
        "parentId": p.get("parent_id"),
    }


def _map_tag(t: dict) -> dict:
    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "color": t.get("color"),
    }


@returns("task[]")
@connection("api")
def list_tasks(*, query: str = "today | overdue | #Inbox", **params) -> list:
    """List actionable tasks (due today, overdue, or in inbox)

        Args:
            query: Todoist filter query
        """
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/tasks/filter",
                    params={"query": query}, **http.headers(accept="json", extra=headers))
    return [_map_task(t) for t in (resp["json"] or {}).get("results", [])]


@returns("task[]")
@connection("api")
def list_all_tasks(*, project_id: str = None, section_id: str = None,
                   parent_id: str = None, label: str = None, **params) -> list:
    """List all tasks with optional filters (no smart defaults)

        Args:
            project_id: Filter by project ID
            section_id: Filter by section ID
            parent_id: Filter by parent task ID
            label: Filter by label name
        """
    headers = _auth_header(params)
    q = {}
    if project_id: q["project_id"] = project_id
    if section_id: q["section_id"] = section_id
    if parent_id: q["parent_id"] = parent_id
    if label: q["label"] = label
    resp = http.get(f"{API_BASE}/tasks", params=q, **http.headers(accept="json", extra=headers))
    return [_map_task(t) for t in (resp["json"] or {}).get("results", [])]


@returns("task[]")
@connection("api")
def filter_task(*, filter: str, **params) -> list:
    """Get tasks matching a Todoist filter query

        Args:
            filter: Todoist filter (e.g., 'today', 'overdue', '7 days')
        """
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/tasks/filter",
                    params={"query": filter}, **http.headers(accept="json", extra=headers))
    return [_map_task(t) for t in (resp["json"] or {}).get("results", [])]


@returns("task")
@provides(web_read, urls=["app.todoist.com/*/task/*", "todoist.com/*/task/*"])
@connection("api")
def get_task(*, id: str = None, url: str = None, **params) -> dict:
    """Get a specific task by ID

        Args:
            id: Task ID — optional if url is an app.todoist.com task link
            url: Todoist task URL from the app (web_read)
        """
    headers = _auth_header(params)
    if url:
        m = re.search(r"/task/([^/?#]+)", url)
        if m:
            id = m.group(1)
    resp = http.get(f"{API_BASE}/tasks/{id}", **http.headers(accept="json", extra=headers))
    return _map_task(resp["json"])


@returns("task")
@connection("api")
def create_task(*, name: str, description: str = None, due: str = None,
                priority: int = None, project_id: str = None,
                parent_id: str = None, labels: list = None, **params) -> dict:
    """Create a new task

        Args:
            name: Task name
            description: Task description
            due: Due date (natural language like 'tomorrow')
            priority: Priority 1 (highest) to 4 (lowest)
            project_id: Project ID
            parent_id: Parent task ID (for sub-tasks)
            labels: Label names
        """
    headers = _auth_header(params)
    body = {"content": name}
    if description is not None: body["description"] = description
    if due is not None: body["due_string"] = due
    if priority is not None: body["priority"] = 5 - priority
    if project_id is not None: body["project_id"] = project_id
    if parent_id is not None: body["parent_id"] = parent_id
    if labels is not None: body["labels"] = labels
    resp = http.post(f"{API_BASE}/tasks", json=body, **http.headers(accept="json", extra=headers))
    return _map_task(resp["json"])


@returns("task")
@connection("api")
def update_task(*, id: str, name: str = None, description: str = None,
                due: str = None, priority: int = None, labels: list = None,
                project_id: str = None, **params) -> dict:
    """Update an existing task (including moving to different project)

        Args:
            id: Task ID
            name: New name
            description: New description
            due: New due date
            priority: New priority 1 (highest) to 4 (lowest)
            labels: New labels
            project_id: Move to different project
        """
    headers = _auth_header(params)
    body = {}
    if name is not None: body["content"] = name
    if description is not None: body["description"] = description
    if due is not None: body["due_string"] = due
    if priority is not None: body["priority"] = 5 - priority
    if labels is not None: body["labels"] = labels
    if project_id is not None: body["project_id"] = project_id
    resp = http.post(f"{API_BASE}/tasks/{id}", json=body, **http.headers(accept="json", extra=headers))
    return _map_task(resp["json"])


@returns({"ok": "boolean"})
@connection("api")
def complete_task(*, id: str, **params) -> None:
    """Mark a task as achieved

        Args:
            id: Task ID
        """
    headers = _auth_header(params)
    http.post(f"{API_BASE}/tasks/{id}/close", **http.headers(accept="json", extra=headers))


@returns({"ok": "boolean"})
@connection("api")
def reopen_task(*, id: str, **params) -> None:
    """Reopen a task

        Args:
            id: Task ID
        """
    headers = _auth_header(params)
    http.post(f"{API_BASE}/tasks/{id}/reopen", **http.headers(accept="json", extra=headers))


@returns({"ok": "boolean"})
@connection("api")
def delete_task(*, id: str, **params) -> None:
    """Delete a task

        Args:
            id: Task ID
        """
    headers = _auth_header(params)
    http.delete(f"{API_BASE}/tasks/{id}", **http.headers(accept="json", extra=headers))


@returns("project[]")
@connection("api")
def list_projects(**params) -> list:
    """List all projects"""
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/projects", **http.headers(accept="json", extra=headers))
    return [_map_project(p) for p in (resp["json"] or {}).get("results", [])]


@returns("tag[]")
@connection("api")
def list_tags(**params) -> list:
    """List all tags (labels)"""
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/labels", **http.headers(accept="json", extra=headers))
    return [_map_tag(t) for t in (resp["json"] or {}).get("results", [])]


@returns("task")
@connection("api")
def move_task(*, id: str, project_id: str = None, section_id: str = None,
              parent_id: str = None, **params) -> dict:
    """Move task to a different project, section, or parent

        Args:
            id: Task ID to move
            project_id: Target project ID
            section_id: Target section ID
            parent_id: Target parent task ID
        """
    headers = _auth_header(params)
    body = {}
    if project_id is not None: body["project_id"] = project_id
    if section_id is not None: body["section_id"] = section_id
    if parent_id is not None: body["parent_id"] = parent_id
    resp = http.post(f"{API_BASE}/tasks/{id}/move", json=body, **http.headers(accept="json", extra=headers))
    return _map_task(resp["json"])
