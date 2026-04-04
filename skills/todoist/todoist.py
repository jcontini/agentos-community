import re
from agentos import http

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


def list_tasks(*, query: str = "today | overdue | #Inbox", **params) -> list:
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/tasks/filter",
                    params={"query": query}, **http.headers(accept="json", extra=headers))
    return [_map_task(t) for t in (resp["json"] or {}).get("results", [])]


def list_all_tasks(*, project_id: str = None, section_id: str = None,
                   parent_id: str = None, label: str = None, **params) -> list:
    headers = _auth_header(params)
    q = {}
    if project_id: q["project_id"] = project_id
    if section_id: q["section_id"] = section_id
    if parent_id: q["parent_id"] = parent_id
    if label: q["label"] = label
    resp = http.get(f"{API_BASE}/tasks", params=q, **http.headers(accept="json", extra=headers))
    return [_map_task(t) for t in (resp["json"] or {}).get("results", [])]


def filter_task(*, filter: str, **params) -> list:
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/tasks/filter",
                    params={"query": filter}, **http.headers(accept="json", extra=headers))
    return [_map_task(t) for t in (resp["json"] or {}).get("results", [])]


def get_task(*, id: str = None, url: str = None, **params) -> dict:
    headers = _auth_header(params)
    if url:
        m = re.search(r"/task/([^/?#]+)", url)
        if m:
            id = m.group(1)
    resp = http.get(f"{API_BASE}/tasks/{id}", **http.headers(accept="json", extra=headers))
    return _map_task(resp["json"])


def create_task(*, name: str, description: str = None, due: str = None,
                priority: int = None, project_id: str = None,
                parent_id: str = None, labels: list = None, **params) -> dict:
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


def update_task(*, id: str, name: str = None, description: str = None,
                due: str = None, priority: int = None, labels: list = None,
                project_id: str = None, **params) -> dict:
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


def complete_task(*, id: str, **params) -> None:
    headers = _auth_header(params)
    http.post(f"{API_BASE}/tasks/{id}/close", **http.headers(accept="json", extra=headers))


def reopen_task(*, id: str, **params) -> None:
    headers = _auth_header(params)
    http.post(f"{API_BASE}/tasks/{id}/reopen", **http.headers(accept="json", extra=headers))


def delete_task(*, id: str, **params) -> None:
    headers = _auth_header(params)
    http.delete(f"{API_BASE}/tasks/{id}", **http.headers(accept="json", extra=headers))


def list_projects(**params) -> list:
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/projects", **http.headers(accept="json", extra=headers))
    return [_map_project(p) for p in (resp["json"] or {}).get("results", [])]


def list_tags(**params) -> list:
    headers = _auth_header(params)
    resp = http.get(f"{API_BASE}/labels", **http.headers(accept="json", extra=headers))
    return [_map_tag(t) for t in (resp["json"] or {}).get("results", [])]


def move_task(*, id: str, project_id: str = None, section_id: str = None,
              parent_id: str = None, **params) -> dict:
    headers = _auth_header(params)
    body = {}
    if project_id is not None: body["project_id"] = project_id
    if section_id is not None: body["section_id"] = section_id
    if parent_id is not None: body["parent_id"] = parent_id
    resp = http.post(f"{API_BASE}/tasks/{id}/move", json=body, **http.headers(accept="json", extra=headers))
    return _map_task(resp["json"])
