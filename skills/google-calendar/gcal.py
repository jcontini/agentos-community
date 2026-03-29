"""Google Calendar skill — all operations via http.get/post/patch/delete.

Auth token lives in params["auth"]["access_token"], injected by the engine
from the Mimestream OAuth provider (googleapis.com / calendar.events scope).
"""

import base64
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from agentos import http

BASE_URL = "https://www.googleapis.com/calendar/v3"


# ==============================================================================
# Internal helpers
# ==============================================================================


def _auth_header(params):
    auth = params.get("auth", {})
    bearer = auth.get("bearer")
    if bearer:
        return {"Authorization": bearer}
    token = auth.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _map_event(event):
    """Map Google Calendar event to agentOS meeting shape."""
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "name": event.get("summary", "(No title)"),
        "text": event.get("description", ""),
        "url": event.get("htmlLink"),
        "start_date": start.get("dateTime") or start.get("date"),
        "end_date": end.get("dateTime") or end.get("date"),
        "timezone": start.get("timeZone"),
        "all_day": "date" in start and "dateTime" not in start,
        "location": event.get("location"),
        "calendar_link": event.get("htmlLink"),
        "is_virtual": bool(event.get("conferenceData")),
        "meeting_url": _extract_meeting_url(event),
        "recurrence": (event.get("recurrence") or [None])[0],
        "organizer": _map_person(event.get("organizer")),
        "involves": [_map_person(a) for a in event.get("attendees", [])],
    }


def _map_person(person):
    if not person:
        return None
    return {
        "handle": person.get("email"),
        "platform": "email",
        "display_name": person.get("displayName", ""),
    }


def _extract_meeting_url(event):
    """Pull video conference URL from conferenceData."""
    cd = event.get("conferenceData")
    if not cd:
        return None
    for ep in cd.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri")
    return None


def _is_date_only(s):
    """Check if string looks like YYYY-MM-DD (all-day) vs datetime."""
    return bool(s and re.match(r"^\d{4}-\d{2}-\d{2}$", s))


def _build_time_body(dt_str, tz=None):
    """Build a start/end object for the Google Calendar API."""
    if _is_date_only(dt_str):
        return {"date": dt_str}
    body = {"dateTime": dt_str}
    if tz:
        body["timeZone"] = tz
    return body


def _extract_event_id_from_url(url):
    """Extract event ID from a Google Calendar URL.

    Google Calendar URLs encode the event ID in the `eid` query param
    as base64(eventId + " " + calendarId).
    """
    if not url:
        return None
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    eid = qs.get("eid", [None])[0]
    if eid:
        try:
            # eid is base64-encoded "eventId calendarId"
            decoded = base64.b64decode(eid + "==").decode("utf-8")
            return decoded.split(" ")[0]
        except Exception:
            return eid
    # Fallback: last path segment
    parts = [p for p in parsed.path.split("/") if p]
    return parts[-1] if parts else None


# ==============================================================================
# Operations
# ==============================================================================


def list_calendars(**params):
    """List all calendars the user can see."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/users/me/calendarList", headers=headers, profile="api")
    items = (resp["json"] or {}).get("items", [])
    return [
        {
            "id": c.get("id"),
            "name": c.get("summary"),
            "color": c.get("backgroundColor"),
            "is_readonly": c.get("accessRole") in ("freeBusyReader", "reader"),
            "is_primary": c.get("primary", False),
            "timezone": c.get("timeZone"),
        }
        for c in items
    ]


def list_events(*, calendar_id="primary", days=7, past=False,
                query=None, limit=50, page_token=None,
                exclude_all_day=False, **params):
    """List events within a date range, optionally filtered by search."""
    headers = _auth_header(params)
    now = datetime.now(timezone.utc)

    if past:
        time_min = (now - timedelta(days=days)).isoformat()
        time_max = now.isoformat()
    else:
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days)).isoformat()

    query_params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "maxResults": str(limit),
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    if query:
        query_params["q"] = query
    if page_token:
        query_params["pageToken"] = page_token

    resp = http.get(
        f"{BASE_URL}/calendars/{calendar_id}/events",
        params=query_params, headers=headers, profile="api",
    )
    data = resp["json"] or {}
    events = [_map_event(e) for e in data.get("items", [])]

    if exclude_all_day:
        events = [e for e in events if not e["all_day"]]

    return events


def get_event(*, id=None, url=None, calendar_id="primary", **params):
    """Get full details of a specific event."""
    if url and not id:
        id = _extract_event_id_from_url(url)
    if not id:
        raise ValueError("Either id or url is required")

    headers = _auth_header(params)
    resp = http.get(
        f"{BASE_URL}/calendars/{calendar_id}/events/{id}",
        headers=headers, profile="api",
    )
    return _map_event(resp["json"])


def create_event(*, title, start, end=None, all_day=None, calendar_id="primary",
                 location=None, description=None, attendees=None,
                 recurrence=None, timezone=None, **params):
    """Create a new calendar event."""
    headers = _auth_header(params)

    # Determine if all-day from the start format
    if all_day or _is_date_only(start):
        start_body = {"date": start}
        if end:
            end_body = {"date": end}
        else:
            # All-day events: end is exclusive, so next day
            end_body = {"date": _next_day(start)}
    else:
        start_body = _build_time_body(start, timezone)
        if end:
            end_body = _build_time_body(end, timezone)
        else:
            # Default: 1 hour after start
            end_body = _build_time_body(_add_one_hour(start), timezone)

    body = {
        "summary": title,
        "start": start_body,
        "end": end_body,
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    if attendees:
        body["attendees"] = [{"email": e} for e in attendees]
    if recurrence:
        body["recurrence"] = recurrence

    resp = http.post(
        f"{BASE_URL}/calendars/{calendar_id}/events",
        json=body, headers=headers, profile="api",
    )
    return _map_event(resp["json"])


def update_event(*, id, calendar_id="primary", title=None, start=None, end=None,
                 location=None, description=None, attendees=None, **params):
    """Update an existing event (PATCH — only provided fields change)."""
    headers = _auth_header(params)

    body = {}
    if title is not None:
        body["summary"] = title
    if start is not None:
        body["start"] = _build_time_body(start)
    if end is not None:
        body["end"] = _build_time_body(end)
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description
    if attendees is not None:
        body["attendees"] = [{"email": e} for e in attendees]

    resp = http.patch(
        f"{BASE_URL}/calendars/{calendar_id}/events/{id}",
        json=body, headers=headers, profile="api",
    )
    return _map_event(resp["json"])


def search_events(*, calendar_id="primary", days=30, past=False,
                   query=None, limit=25, **params):
    """Search events — thin wrapper over list_events with search-oriented defaults."""
    return list_events(
        calendar_id=calendar_id, days=days, past=past,
        query=query, limit=limit, **params,
    )


def delete_event(*, id, calendar_id="primary", **params):
    """Delete a calendar event."""
    headers = _auth_header(params)
    http.delete(
        f"{BASE_URL}/calendars/{calendar_id}/events/{id}",
        headers=headers, profile="api",
    )
    return {"status": "deleted"}


# ==============================================================================
# Date helpers
# ==============================================================================


def _next_day(date_str):
    """Given YYYY-MM-DD, return the next day."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=1)).strftime("%Y-%m-%d")


def _add_one_hour(dt_str):
    """Add one hour to an ISO datetime string."""
    # Handle with or without timezone offset
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            d = datetime.strptime(dt_str, fmt)
            return (d + timedelta(hours=1)).strftime(fmt.replace("%z", "")) + (
                dt_str[19:] if len(dt_str) > 19 and fmt.endswith("%z") else ""
            )
        except ValueError:
            continue
    # Fallback: just append T+1h naively
    return dt_str
