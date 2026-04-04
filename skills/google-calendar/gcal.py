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

VIRTUAL_PATTERNS = [
    (r'https?://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}', 'Google Meet'),
    (r'https?://(?:[a-z0-9]+\.)?zoom\.us/(?:j|my)/\S+', 'Zoom'),
    (r'https?://teams\.microsoft\.com/l/meetup-join/\S+', 'Microsoft Teams'),
    (r'https?://(?:[a-z0-9]+\.)?webex\.com/(?:meet|join)/\S+', 'WebEx'),
    (r'https?://(?:[a-z0-9]+\.)?goto\.(?:com|meeting)/\S+', 'GoTo Meeting'),
]


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


def _clean_html(text):
    """Convert HTML description to plain text via lxml."""
    if not text or "<" not in text:
        return text or ""
    try:
        from lxml import html as lxml_html
        from lxml import etree
        doc = lxml_html.fromstring(text)
        # Insert newlines after block elements so text_content() doesn't merge them
        for el in doc.iter():
            if el.tag in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                          'li', 'tr', 'blockquote', 'pre', 'hr'):
                if el.tail is None:
                    el.tail = '\n'
                elif not el.tail.startswith('\n'):
                    el.tail = '\n' + el.tail
        result = doc.text_content()
        # Collapse multiple blank lines, strip
        lines = [line.strip() for line in result.splitlines()]
        return '\n'.join(line for line in lines if line).strip()
    except Exception:
        return text


def _map_location(location_str):
    """Parse location string into a place shape."""
    if not location_str:
        return None
    # Check for virtual meeting URL
    for pattern, provider in VIRTUAL_PATTERNS:
        if re.search(pattern, location_str, re.IGNORECASE):
            return None  # virtual-only, not a physical place
    parts = location_str.split(",", 1)
    name = parts[0].strip()
    has_numbers = bool(re.search(r'\d', name))
    return {
        "name": name,
        "fullAddress": location_str if len(parts) > 1 else None,
        "featureType": "address" if has_numbers else "poi",
    }


def _derive_name_from_email(email):
    """Derive a display name from an email local part."""
    if not email:
        return ""
    local = email.split("@")[0]
    return local.replace(".", " ").replace("_", " ").replace("-", " ").title()


def _map_attendee(att):
    """Map a Google Calendar attendee to a person with RSVP metadata."""
    if not att:
        return None
    email = att.get("email", "")
    name = att.get("displayName") or _derive_name_from_email(email)
    parts = name.split(None, 1) if name else []
    return {
        "name": name,
        "handle": email,
        "firstName": parts[0] if parts else None,
        "lastName": parts[1] if len(parts) > 1 else None,
        "rsvp": att.get("responseStatus"),
        "isSelf": att.get("self", False),
        "isOptional": att.get("optional", False),
        "isOrganizer": att.get("organizer", False),
        "isResource": att.get("resource", False),
        "rsvpComment": att.get("comment"),
        "additionalGuests": att.get("additionalGuests", 0),
    }


def _map_person_from_gcal(person):
    """Map organizer/creator dict to a person shape with name derivation."""
    if not person:
        return None
    email = person.get("email", "")
    name = person.get("displayName") or _derive_name_from_email(email)
    parts = name.split(None, 1) if name else []
    return {
        "name": name,
        "handle": email,
        "firstName": parts[0] if parts else None,
        "lastName": parts[1] if len(parts) > 1 else None,
        "isSelf": person.get("self", False),
    }


def _derive_show_as(event):
    """Derive availability status from event fields."""
    etype = event.get("eventType", "default")
    transp = event.get("transparency", "opaque")
    if etype == "outOfOffice":
        return "out_of_office"
    if etype == "focusTime":
        return "busy"
    if etype == "workingLocation":
        return "working_elsewhere"
    if transp == "transparent":
        return "free"
    status = event.get("status", "confirmed")
    if status == "tentative":
        return "tentative"
    return "busy"


def _map_conference(event):
    """Extract all conference entry points — video, phone, SIP, access codes."""
    cd = event.get("conferenceData")
    if not cd:
        return None, None, None, []

    meeting_url = None
    phone_dial_in = None
    entry_points = []

    for ep in cd.get("entryPoints", []):
        entry = {
            "type": ep.get("entryPointType"),
            "uri": ep.get("uri"),
            "label": ep.get("label"),
            "pin": ep.get("pin"),
            "accessCode": ep.get("accessCode"),
        }
        entry_points.append(entry)
        if ep.get("entryPointType") == "video":
            meeting_url = ep.get("uri")
        elif ep.get("entryPointType") == "phone":
            phone_dial_in = ep.get("uri")

    solution = cd.get("conferenceSolution", {})
    provider = solution.get("name")  # "Google Meet", "Zoom", etc.

    return meeting_url, provider, phone_dial_in, entry_points


def _map_attachments(event):
    """Map attachments to file shapes (Drive) and webpage shapes (external URLs)."""
    raw = event.get("attachments", [])
    if not raw:
        return None, None
    attachments = []
    links = []
    for a in raw:
        if a.get("fileId"):
            attachments.append({
                "filename": a.get("title"),
                "mimeType": a.get("mimeType"),
                "url": a.get("fileUrl"),
            })
        else:
            links.append({
                "name": a.get("title"),
                "url": a.get("fileUrl"),
            })
    return attachments or None, links or None


def _map_event(event):
    """Map Google Calendar event to agentOS meeting shape."""
    start = event.get("start", {})
    end = event.get("end", {})
    attendees = event.get("attendees", [])
    etype = event.get("eventType", "default")

    # Conference
    meeting_url, conference_provider, phone_dial_in, conference_entry_points = _map_conference(event)

    # Attachments
    attachments, links = _map_attachments(event)

    # Source provenance
    source = event.get("source")

    # Recurrence — full list, not just first rule
    recurrence_rules = event.get("recurrence")

    # Reminders
    reminders_data = event.get("reminders", {})
    reminders = reminders_data.get("overrides") if not reminders_data.get("useDefault") else None

    out = {
        "id": event.get("id"),
        "name": event.get("summary", "(No title)"),
        "content": _clean_html(event.get("description", "")),
        "url": event.get("htmlLink"),
        "startDate": start.get("dateTime") or start.get("date"),
        "endDate": end.get("dateTime") or end.get("date"),
        "timezone": start.get("timeZone"),
        "allDay": "date" in start and "dateTime" not in start,
        "location": _map_location(event.get("location")),
        "calendarLink": event.get("htmlLink"),
        # Conference (R8)
        "isVirtual": bool(event.get("conferenceData")),
        "meetingUrl": meeting_url,
        "conferenceProvider": conference_provider,
        "phoneDialIn": phone_dial_in,
        "conferenceEntryPoints": conference_entry_points or None,
        # Recurrence (R10)
        "recurrence": recurrence_rules,
        "recurringEventId": event.get("recurringEventId"),
        "originalStartTime": (event.get("originalStartTime") or {}).get("dateTime"),
        # Relations
        "organizer": _map_person_from_gcal(event.get("organizer")),
        "author": _map_person_from_gcal(event.get("creator")),
        "involves": [_map_attendee(a) for a in attendees if not a.get("resource")],
        # Status & type (R4-R5)
        "status": event.get("status"),
        "eventType": etype,
        "visibility": event.get("visibility"),
        "showAs": _derive_show_as(event),
        # Timestamps (R6)
        "published": event.get("created"),
        "dateUpdated": event.get("updated"),
        # Identity (R14)
        "icalUid": event.get("iCalUID"),
        "etag": event.get("etag"),
        # Source provenance (R9)
        "sourceUrl": source.get("url") if source else None,
        "sourceTitle": source.get("title") if source else None,
        # Reminders (R11)
        "reminders": reminders,
        # Attachments (R12)
        "attachments": attachments,
        "links": links,
        # Permissions (R18)
        "guestsCanModify": event.get("guestsCanModify"),
        "guestsCanInvite": event.get("guestsCanInviteOthers"),
        "guestsCanSeeOthers": event.get("guestsCanSeeOtherGuests"),
    }

    # Birthday → life event (R13)
    if etype == "birthday":
        bp = event.get("birthdayProperties", {})
        out["birthday_contact_id"] = bp.get("contact")
        out["birthday_type"] = bp.get("type")

    # Focus time properties (R16)
    if etype == "focusTime":
        fp = event.get("focusTimeProperties", {})
        out["auto_decline"] = fp.get("autoDeclineMode")
        out["chat_status"] = fp.get("chatStatus")

    # Out of office properties (R16)
    if etype == "outOfOffice":
        ooo = event.get("outOfOfficeProperties", {})
        out["auto_decline"] = ooo.get("autoDeclineMode")
        out["decline_message"] = ooo.get("declineMessage")

    # Working location properties (R16)
    if etype == "workingLocation":
        wl = event.get("workingLocationProperties", {})
        out["working_location_type"] = wl.get("type")

    return out


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


def list_calendars(*, account=None, **params):
    """List all calendars the user can see."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/users/me/calendarList", **http.headers(accept="json", extra=headers))
    items = (resp["json"] or {}).get("items", [])
    return [
        {
            "id": c.get("id"),
            "name": c.get("summary"),
            "color": c.get("backgroundColor"),
            "isReadonly": c.get("accessRole") in ("freeBusyReader", "reader"),
            "isPrimary": c.get("primary", False),
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
        params=query_params, **http.headers(accept="json", extra=headers),
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
        **http.headers(accept="json", extra=headers),
    )
    return _map_event(resp["json"])


def create_event(*, title, start, end=None, all_day=None, calendar_id="primary",
                 location=None, description=None, attendees=None,
                 recurrence=None, timezone=None, meet=False, **params):
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
    if meet:
        import uuid
        body["conferenceData"] = {
            "createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    url = f"{BASE_URL}/calendars/{calendar_id}/events"
    if meet:
        url += "?conferenceDataVersion=1"

    resp = http.post(
        url,
        json=body, **http.headers(accept="json", extra=headers),
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
        json=body, **http.headers(accept="json", extra=headers),
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
        **http.headers(accept="json", extra=headers),
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
