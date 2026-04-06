"""PostHog — product analytics: persons, events, recordings, and HogQL queries."""

from agentos import http, connection, returns

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
        "published": p.get("created_at"),
        "distinctIds": distinct_ids,
        "lastSeenAt": p.get("last_seen_at"),
        "browser": props.get("$browser"),
        "os": props.get("$os"),
        "initialReferrer": props.get("$initial_referrer"),
        "initialUtmSource": props.get("$initial_utm_source"),
    }


def _map_event(e: dict) -> dict:
    props = e.get("properties") or {}
    return {
        "id": e.get("id"),
        "name": e.get("event"),
        "published": e.get("timestamp"),
        "content": ", ".join(props.keys()),
        "distinctId": e.get("distinct_id"),
        "properties": props,
        "currentUrl": props.get("$current_url"),
        "person": e.get("person"),
    }


@returns("person[]")
@connection("api")
def list_persons(*, project_id: str, search: str = None, limit: int = None, offset: int = None, **params) -> list[dict]:
    """List persons in a project

        Args:
            project_id: PostHog project ID
            search: Search by email or name
        """
    q: dict = {}
    if search:
        q["search"] = search
    if limit is not None:
        q["limit"] = str(limit)
    if offset is not None:
        q["offset"] = str(offset)
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/persons/",
                    params=q, **http.headers(accept="json", extra=_auth_header(params)))
    return [_map_person(p) for p in (resp["json"] or {}).get("results", [])]


@returns("person")
@connection("api")
def get_person(*, project_id: str, id: str, **params) -> dict:
    """Get a person by UUID

        Args:
            project_id: PostHog project ID
            id: Person UUID
        """
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/persons/{id}/",
                    **http.headers(accept="json", extra=_auth_header(params)))
    return _map_person(resp["json"])


@returns("person[]")
@connection("api")
def search_persons(*, project_id: str, query: str, limit: int = None, **params) -> list[dict]:
    """Search persons by email or name

        Args:
            project_id: PostHog project ID
            query: Email or name to search for
        """
    q: dict = {"search": query}
    if limit is not None:
        q["limit"] = str(limit)
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/persons/",
                    params=q, **http.headers(accept="json", extra=_auth_header(params)))
    return [_map_person(p) for p in (resp["json"] or {}).get("results", [])]


@returns("event[]")
@connection("api")
def list_events(*, project_id: str, event: str = None, limit: int = None, after: str = None, before: str = None, **params) -> list[dict]:
    """List recent events (deprecated API — use query utility for complex queries)

        Args:
            project_id: PostHog project ID
            event: Filter by event name
            after: ISO datetime — only events after this time
            before: ISO datetime — only events before this time
        """
    q: dict = {}
    if event:
        q["event"] = event
    if limit is not None:
        q["limit"] = str(limit)
    if after:
        q["after"] = after
    if before:
        q["before"] = before
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/events/",
                    params=q, **http.headers(accept="json", extra=_auth_header(params)))
    return [_map_event(e) for e in (resp["json"] or {}).get("results", [])]


@returns("event")
@connection("api")
def get_event(*, project_id: str, id: str, **params) -> dict:
    """Get a single event by ID

        Args:
            project_id: PostHog project ID
            id: Event ID
        """
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/events/{id}/",
                    **http.headers(accept="json", extra=_auth_header(params)))
    return _map_event(resp["json"])


@returns({"id": "integer", "uuid": "string", "name": "string", "apiToken": "string"})
@connection("api")
def get_projects(**params) -> list[dict]:
    """List all projects the authenticated user has access to"""
    resp = http.get(f"{POSTHOG_BASE}/api/projects/",
                    **http.headers(accept="json", extra=_auth_header(params)))
    return (resp["json"] or {}).get("results", [])


@returns({"columns": "array", "results": "array", "types": "array"})
@connection("api")
def query(*, project_id: str, hogql: str, **params) -> dict:
    """Run a HogQL query against the events table (recommended over events API)

        Args:
            project_id: PostHog project ID
            hogql: HogQL query string
        """
    resp = http.post(f"{POSTHOG_BASE}/api/projects/{project_id}/query/",
                     json={"query": {"kind": "HogQLQuery", "query": hogql}},
                     **http.headers(accept="json", extra=_auth_header(params)))
    return resp["json"]


@returns({"id": "string", "name": "string", "volume_30_day": "integer", "queryUsage30Day": "integer"})
@connection("api")
def get_event_definitions(*, project_id: str, limit: int = None, **params) -> list[dict]:
    """List all event names defined in a project

        Args:
            project_id: PostHog project ID
        """
    q: dict = {}
    if limit is not None:
        q["limit"] = str(limit)
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/event_definitions/",
                    params=q, **http.headers(accept="json", extra=_auth_header(params)))
    return (resp["json"] or {}).get("results", [])


@returns({"id": "string", "distinctId": "string", "startTime": "string", "endTime": "string", "recordingDuration": "number", "activeSeconds": "number", "clickCount": "integer", "keypressCount": "integer", "startUrl": "string", "viewed": "boolean"})
@connection("api")
def list_recordings(*, project_id: str, limit: int = None, offset: int = None, **params) -> list[dict]:
    """List session recordings for a project

        Args:
            project_id: PostHog project ID
        """
    q: dict = {}
    if limit is not None:
        q["limit"] = str(limit)
    if offset is not None:
        q["offset"] = str(offset)
    resp = http.get(f"{POSTHOG_BASE}/api/projects/{project_id}/session_recordings/",
                    params=q, **http.headers(accept="json", extra=_auth_header(params)))
    return (resp["json"] or {}).get("results", [])
