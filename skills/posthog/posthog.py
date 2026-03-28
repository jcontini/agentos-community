"""PostHog — product analytics: persons, events, recordings, and HogQL queries."""

from agentos import surf

POSTHOG_BASE = "https://us.posthog.com"


def _auth_header(params: dict) -> dict:
    key = params.get("auth", {}).get("key", "")
    return {"Authorization": f"Bearer {key}"}


def _map_person(p: dict) -> dict:
    props = p.get("properties") or {}
    distinct_ids = p.get("distinct_ids") or []
    return {
        "id": p.get("uuid"),
        "name": props.get("name") or props.get("email") or (distinct_ids[0] if distinct_ids else None) or "Unknown",
        "email": props.get("email"),
        "datePublished": p.get("created_at"),
        "distinct_ids": distinct_ids,
        "last_seen_at": p.get("last_seen_at"),
        "browser": props.get("$browser"),
        "os": props.get("$os"),
        "initial_referrer": props.get("$initial_referrer"),
        "initial_utm_source": props.get("$initial_utm_source"),
    }


def _map_event(e: dict) -> dict:
    props = e.get("properties") or {}
    return {
        "id": e.get("id"),
        "name": e.get("event"),
        "datePublished": e.get("timestamp"),
        "text": ", ".join(props.keys()),
        "distinct_id": e.get("distinct_id"),
        "properties": props,
        "current_url": props.get("$current_url"),
        "person": e.get("person"),
    }


def list_persons(*, project_id: str, search: str = None, limit: int = None, offset: int = None, **params) -> list[dict]:
    q: dict = {}
    if search:
        q["search"] = search
    if limit is not None:
        q["limit"] = str(limit)
    if offset is not None:
        q["offset"] = str(offset)
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/persons/",
            params=q,
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return [_map_person(p) for p in resp.json().get("results", [])]


def get_person(*, project_id: str, id: str, **params) -> dict:
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/persons/{id}/",
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return _map_person(resp.json())


def search_persons(*, project_id: str, query: str, limit: int = None, **params) -> list[dict]:
    q: dict = {"search": query}
    if limit is not None:
        q["limit"] = str(limit)
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/persons/",
            params=q,
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return [_map_person(p) for p in resp.json().get("results", [])]


def list_events(*, project_id: str, event: str = None, limit: int = None, after: str = None, before: str = None, **params) -> list[dict]:
    q: dict = {}
    if event:
        q["event"] = event
    if limit is not None:
        q["limit"] = str(limit)
    if after:
        q["after"] = after
    if before:
        q["before"] = before
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/events/",
            params=q,
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return [_map_event(e) for e in resp.json().get("results", [])]


def get_event(*, project_id: str, id: str, **params) -> dict:
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/events/{id}/",
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return _map_event(resp.json())


def get_projects(**params) -> list[dict]:
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/",
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return resp.json().get("results", [])


def query(*, project_id: str, hogql: str, **params) -> dict:
    with surf(profile="api") as client:
        resp = client.post(
            f"{POSTHOG_BASE}/api/projects/{project_id}/query/",
            json={"query": {"kind": "HogQLQuery", "query": hogql}},
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return resp.json()


def get_event_definitions(*, project_id: str, limit: int = None, **params) -> list[dict]:
    q: dict = {}
    if limit is not None:
        q["limit"] = str(limit)
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/event_definitions/",
            params=q,
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return resp.json().get("results", [])


def list_recordings(*, project_id: str, limit: int = None, offset: int = None, **params) -> list[dict]:
    q: dict = {}
    if limit is not None:
        q["limit"] = str(limit)
    if offset is not None:
        q["offset"] = str(offset)
    with surf(profile="api") as client:
        resp = client.get(
            f"{POSTHOG_BASE}/api/projects/{project_id}/session_recordings/",
            params=q,
            headers=_auth_header(params),
        )
        resp.raise_for_status()
    return resp.json().get("results", [])
