"""Gmail skill — all operations implemented via http.get()/http.post()/etc.

All public functions take **params. Auth token lives in
params["auth"]["access_token"], injected by the engine from OAuth resolution.
"""

import base64
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from agentos import http

BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


# ==============================================================================
# Internal helpers
# ==============================================================================


def _auth_header(params):
    auth = params.get("auth", {})
    # Engine injects "bearer" (full header) and "access_token" (raw token)
    bearer = auth.get("bearer")
    if bearer:
        return {"Authorization": bearer}
    token = auth.get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _get_header(headers, name):
    """Find a header by name (case-insensitive), return its value or None."""
    name_lower = name.lower()
    for h in headers or []:
        if h.get("name", "").lower() == name_lower:
            return h.get("value")
    return None


def _parse_addresses(header_val):
    """Parse 'Name <email>, Name2 <email2>' into list of {handle, display_name}.

    Splits on '>, ' first to avoid breaking names that contain commas.
    """
    if not header_val:
        return []
    results = []
    # Split on '>, ' keeping the '>' with the preceding segment
    parts = re.split(r">,\s*", header_val)
    for part in parts:
        part = part.strip().rstrip(">")
        if not part:
            continue
        if "<" in part:
            name_part, email_part = part.split("<", 1)
            email = email_part.rstrip(">").strip()
            display_name = name_part.strip().strip('"').strip("'").strip()
        elif "@" in part:
            email = part.strip()
            display_name = ""
        else:
            continue
        results.append(
            {
                "handle": email,
                "platform": "email",
                "display_name": display_name or None,
            }
        )
    return results


def _decode_body_text(payload):
    """Find the text/plain part and base64url-decode its content.

    Handles flat payloads (single part) and nested multipart structures.
    """
    if not payload:
        return ""

    def _find_plain(part):
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = (part.get("body") or {}).get("data", "")
            if data:
                # Add padding if needed
                padded = data + "=" * ((4 - len(data) % 4) % 4)
                try:
                    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
                except Exception:
                    return ""
        if mime.startswith("multipart/"):
            for sub in part.get("parts") or []:
                result = _find_plain(sub)
                if result:
                    return result
        return ""

    # Try parts first (multipart), then the payload itself
    for sub in payload.get("parts") or []:
        result = _find_plain(sub)
        if result:
            return result
    return _find_plain(payload)


def _collect_attachments(payload):
    """Recursively collect attachment metadata from MIME parts."""
    results = []
    if not payload:
        return results

    def _walk(part):
        filename = part.get("filename")
        body = part.get("body") or {}
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            results.append(
                {
                    "filename": filename,
                    "mime_type": part.get("mimeType"),
                    "size": body.get("size"),
                    "attachment_id": attachment_id,
                }
            )
        for sub in part.get("parts") or []:
            _walk(sub)

    _walk(payload)
    return results


def _internaldate_to_iso(internal_date):
    """Convert Gmail internalDate (ms since epoch string) to ISO 8601."""
    if not internal_date:
        return None
    try:
        ts = int(internal_date) / 1000
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _map_email(msg):
    """Map a Gmail message object to the agentOS email shape."""
    if not msg:
        return msg
    payload = msg.get("payload") or {}
    headers = payload.get("headers") or []
    label_ids = msg.get("labelIds") or []

    subject = _get_header(headers, "Subject") or "(no subject)"
    from_raw = _get_header(headers, "From") or ""

    # Parse From for display_name and email
    from_parsed = _parse_addresses(from_raw)
    from_obj = from_parsed[0] if from_parsed else {"handle": from_raw, "platform": "email", "display_name": None}

    # Author: display name before '<', or None
    if "<" in from_raw:
        author = from_raw.split("<")[0].strip().strip('"').strip("'").strip() or None
    else:
        author = None

    return {
        "id": msg.get("id"),
        "name": subject,
        "text": msg.get("snippet", ""),
        "author": author,
        "datePublished": _internaldate_to_iso(msg.get("internalDate")),
        "is_starred": "STARRED" in label_ids,
        "is_unread": "UNREAD" in label_ids,
        "is_draft": "DRAFT" in label_ids,
        "message_id": _get_header(headers, "Message-ID") or "",
        "in_reply_to": _get_header(headers, "In-Reply-To"),
        "conversation_id": msg.get("threadId", ""),
        "content": _decode_body_text(payload),
        "label_ids": label_ids,
        "size_estimate": msg.get("sizeEstimate"),
        "history_id": msg.get("historyId"),
        "references": _get_header(headers, "References"),
        "reply_to": _get_header(headers, "Reply-To"),
        "delivered_to": _get_header(headers, "Delivered-To"),
        "attachments": _collect_attachments(payload),
        "from": from_obj,
        "to": _parse_addresses(_get_header(headers, "To")),
        "cc": _parse_addresses(_get_header(headers, "Cc")),
        "bcc": _parse_addresses(_get_header(headers, "Bcc")),
    }


def _map_conversation(thread):
    """Map a Gmail thread object to the agentOS conversation shape."""
    if not thread:
        return thread
    messages = thread.get("messages") or []
    snippet = thread.get("snippet", "")

    # Subject from first message
    name = None
    if messages:
        first_headers = (messages[0].get("payload") or {}).get("headers") or []
        name = _get_header(first_headers, "Subject")
    if not name:
        name = snippet[:120] + ("…" if len(snippet) > 120 else "")

    # datePublished from last message
    date_published = None
    if messages:
        date_published = _internaldate_to_iso(messages[-1].get("internalDate"))

    return {
        "id": thread.get("id"),
        "name": name,
        "text": snippet,
        "datePublished": date_published,
        "message_count": len(messages) if messages else None,
        "history_id": thread.get("historyId"),
    }


def _build_raw(to, subject, body_text, html_body=None, cc=None, bcc=None,
               in_reply_to=None, references=None, thread_id=None):
    """Build a base64url-encoded RFC 2822 message for the Gmail API 'raw' field."""
    if html_body:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text or "", "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        msg = MIMEText(body_text or "", "plain", "utf-8")

    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
    return raw


# ==============================================================================
# Read operations
# ==============================================================================


def list_email_stubs(*, query="", limit=20, label_ids=None, page_token=None, **params):
    """List email IDs/stubs only — no full message content."""
    headers = _auth_header(params)
    query_params = {"maxResults": str(limit)}
    if query:
        query_params["q"] = query
    if label_ids:
        query_params["labelIds"] = label_ids
    if page_token:
        query_params["pageToken"] = page_token

    resp = http.get(f"{BASE_URL}/messages", params=query_params, **http.headers(accept="json", extra=headers))
    return resp["json"].get("messages", [])


def get_email(*, id=None, url=None, **params):
    """Get a specific email with full body content, headers, and attachment metadata."""
    # Extract ID from URL if provided
    if url and not id:
        # Fragment is after '#', then last path segment
        fragment = url.split("#")[-1] if "#" in url else url
        id = [seg for seg in fragment.split("/") if seg][-1]

    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/messages/{id}", params={"format": "full"}, **http.headers(accept="json", extra=headers))
    return _map_email(resp["json"])


def list_emails(*, query="", limit=20, label_ids=None, page_token=None, **params):
    """List emails with full content — fetches stubs then hydrates each via get_email."""
    stubs = list_email_stubs(query=query, limit=limit, label_ids=label_ids,
                             page_token=page_token, **params)
    if not stubs:
        return []
    return [get_email(id=s["id"], **params) for s in stubs]


def search_emails(*, query, limit=20, **params):
    """Search emails with full content using Gmail query syntax."""
    stubs = list_email_stubs(query=query, limit=limit, **params)
    if not stubs:
        return []
    return [get_email(id=s["id"], **params) for s in stubs]


def list_conversations(*, query="", label_ids=None, limit=20, page_token=None, **params):
    """List email threads with snippets."""
    headers = _auth_header(params)
    query_params = {"maxResults": str(limit)}
    if query:
        query_params["q"] = query
    if label_ids:
        query_params["labelIds"] = label_ids
    if page_token:
        query_params["pageToken"] = page_token

    resp = http.get(f"{BASE_URL}/threads", params=query_params, **http.headers(accept="json", extra=headers))
    threads = resp["json"].get("threads", [])
    # Threads from list API only have id/snippet/historyId — map what's available
    return [_map_conversation(t) for t in threads]


def get_conversation(*, id, **params):
    """Get a full email thread with all messages, headers, and body content."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/threads/{id}", params={"format": "full"}, **http.headers(accept="json", extra=headers))
    return _map_conversation(resp["json"])


def get_profile(**params):
    """Get Gmail account profile (email address, message count, history ID)."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/profile", **http.headers(accept="json", extra=headers))
    return resp["json"]


def list_labels(**params):
    """List all Gmail labels (system and user-created)."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/labels", **http.headers(accept="json", extra=headers))
    return resp["json"].get("labels", [])


def get_attachment(*, message_id, attachment_id, **params):
    """Download an email attachment (returns base64url-encoded data)."""
    headers = _auth_header(params)
    resp = http.get(
        f"{BASE_URL}/messages/{message_id}/attachments/{attachment_id}",
        **http.headers(accept="json", extra=headers),
    )
    return resp["json"]


def get_raw(*, id, **params):
    """Get the full RFC 2822 raw source of an email (base64url-encoded)."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/messages/{id}", params={"format": "raw"}, **http.headers(accept="json", extra=headers))
    return resp["json"]


def get_history(*, start_history_id, label_id=None, history_types=None,
                limit=100, page_token=None, **params):
    """Get incremental changes since a history ID."""
    headers = _auth_header(params)
    query_params = {"startHistoryId": str(start_history_id), "maxResults": str(limit)}
    if label_id:
        query_params["labelId"] = label_id
    if history_types:
        query_params["historyTypes"] = history_types
    if page_token:
        query_params["pageToken"] = page_token

    resp = http.get(f"{BASE_URL}/history", params=query_params, **http.headers(accept="json", extra=headers))
    return resp["json"]


def get_vacation(**params):
    """Get vacation/auto-reply settings."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/settings/vacation", **http.headers(accept="json", extra=headers))
    return resp["json"]


def list_drafts(*, query="", limit=20, page_token=None, **params):
    """List drafts."""
    headers = _auth_header(params)
    query_params = {"maxResults": str(limit)}
    if query:
        query_params["q"] = query
    if page_token:
        query_params["pageToken"] = page_token

    resp = http.get(f"{BASE_URL}/drafts", params=query_params, **http.headers(accept="json", extra=headers))
    return resp["json"].get("drafts", [])


def get_draft(*, id, **params):
    """Get a draft with full message content."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/drafts/{id}", params={"format": "full"}, **http.headers(accept="json", extra=headers))
    return resp["json"]


def list_filters(**params):
    """List all server-side email filters/rules."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/settings/filters", **http.headers(accept="json", extra=headers))
    return resp["json"].get("filter", [])


def list_send_as(**params):
    """List send-as aliases (email addresses you can send from)."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/settings/sendAs", **http.headers(accept="json", extra=headers))
    return resp["json"].get("sendAs", [])


# ==============================================================================
# Write operations
# ==============================================================================


def send_email(*, to, subject, body, html_body=None, cc=None, bcc=None, **params):
    """Send a new email (plain text or HTML)."""
    raw = _build_raw(to, subject, body, html_body=html_body, cc=cc, bcc=bcc)
    headers = _auth_header(params)
    resp = http.post(
        f"{BASE_URL}/messages/send",
        json={"raw": raw},
        **http.headers(accept="json", extra=headers),
    )
    return _map_email(resp["json"])


def reply_email(*, to, thread_id, in_reply_to, subject, body, html_body=None,
                cc=None, bcc=None, references=None, **params):
    """Reply to an email (stays in the same thread)."""
    raw = _build_raw(
        to, subject, body,
        html_body=html_body, cc=cc, bcc=bcc,
        in_reply_to=in_reply_to, references=references,
    )
    headers = _auth_header(params)
    resp = http.post(
        f"{BASE_URL}/messages/send",
        json={"raw": raw, "threadId": thread_id},
        **http.headers(accept="json", extra=headers),
    )
    return _map_email(resp["json"])


def forward_email(*, to, subject, body, html_body=None, cc=None, bcc=None,
                  thread_id=None, **params):
    """Forward an email."""
    raw = _build_raw(to, subject, body, html_body=html_body, cc=cc, bcc=bcc)
    headers = _auth_header(params)
    payload = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    resp = http.post(f"{BASE_URL}/messages/send", json=payload, **http.headers(accept="json", extra=headers))
    return _map_email(resp["json"])


def modify_email(*, id, add_labels=None, remove_labels=None, **params):
    """Modify email labels — mark read/unread, star/unstar, archive, move to spam."""
    headers = _auth_header(params)
    body = {
        "addLabelIds": add_labels or [],
        "removeLabelIds": remove_labels or [],
    }
    resp = http.post(f"{BASE_URL}/messages/{id}/modify", json=body, **http.headers(accept="json", extra=headers))
    return _map_email(resp["json"])


def trash_email(*, id, **params):
    """Move an email to trash."""
    headers = _auth_header(params)
    resp = http.post(f"{BASE_URL}/messages/{id}/trash", **http.headers(accept="json", extra=headers))
    return _map_email(resp["json"])


def untrash_email(*, id, **params):
    """Remove an email from trash."""
    headers = _auth_header(params)
    resp = http.post(f"{BASE_URL}/messages/{id}/untrash", **http.headers(accept="json", extra=headers))
    return _map_email(resp["json"])


def batch_modify_email(*, ids, add_labels=None, remove_labels=None, **params):
    """Modify labels on multiple emails at once (max 1000 IDs)."""
    headers = _auth_header(params)
    body = {
        "ids": ids,
        "addLabelIds": add_labels or [],
        "removeLabelIds": remove_labels or [],
    }
    resp = http.post(f"{BASE_URL}/messages/batchModify", json=body, **http.headers(accept="json", extra=headers))
    # 204 No Content on success
    return {}


def batch_delete_email(*, ids, **params):
    """Permanently delete multiple emails (max 1000 IDs). CANNOT BE UNDONE."""
    headers = _auth_header(params)
    resp = http.post(
        f"{BASE_URL}/messages/batchDelete",
        json={"ids": ids},
        **http.headers(accept="json", extra=headers),
    )
    return {}


def create_draft(*, to, subject, body, html_body=None, cc=None, bcc=None,
                 thread_id=None, **params):
    """Create a new draft email."""
    raw = _build_raw(to, subject, body, html_body=html_body, cc=cc, bcc=bcc)
    headers = _auth_header(params)
    message = {"raw": raw}
    if thread_id:
        message["threadId"] = thread_id
    resp = http.post(
        f"{BASE_URL}/drafts",
        json={"message": message},
        **http.headers(accept="json", extra=headers),
    )
    return resp["json"]


def update_draft(*, id, to, subject, body, html_body=None, cc=None, bcc=None, **params):
    """Update an existing draft."""
    raw = _build_raw(to, subject, body, html_body=html_body, cc=cc, bcc=bcc)
    headers = _auth_header(params)
    resp = http.put(
        f"{BASE_URL}/drafts/{id}",
        json={"message": {"raw": raw}},
        **http.headers(accept="json", extra=headers),
    )
    return resp["json"]


def send_draft(*, id, **params):
    """Send an existing draft."""
    headers = _auth_header(params)
    resp = http.post(
        f"{BASE_URL}/drafts/send",
        json={"id": id},
        **http.headers(accept="json", extra=headers),
    )
    return resp["json"]


def delete_draft(*, id, **params):
    """Permanently delete a draft."""
    headers = _auth_header(params)
    resp = http.delete(f"{BASE_URL}/drafts/{id}", **http.headers(accept="json", extra=headers))
    return {"status": "deleted"}


def set_vacation(*, enabled, subject=None, body=None, html_body=None,
                 contacts_only=False, domain_only=False,
                 start_time=None, end_time=None, **params):
    """Set or disable vacation/auto-reply."""
    headers = _auth_header(params)
    payload = {
        "enableAutoReply": enabled,
        "responseSubject": subject or "",
        "responseBodyPlainText": body or "",
        "responseBodyHtml": html_body or "",
        "restrictToContacts": contacts_only or False,
        "restrictToDomain": domain_only or False,
    }
    if start_time is not None:
        payload["startTime"] = start_time
    if end_time is not None:
        payload["endTime"] = end_time

    resp = http.put(f"{BASE_URL}/settings/vacation", json=payload, **http.headers(accept="json", extra=headers))
    return resp["json"]


def create_label(*, name, show_in_label_list=None, show_in_message_list=None, **params):
    """Create a new Gmail label."""
    headers = _auth_header(params)
    payload = {
        "name": name,
        "labelListVisibility": show_in_label_list or "labelShow",
        "messageListVisibility": show_in_message_list or "show",
    }
    resp = http.post(f"{BASE_URL}/labels", json=payload, **http.headers(accept="json", extra=headers))
    return resp["json"]


def update_label(*, id, name=None, show_in_label_list=None, show_in_message_list=None, **params):
    """Update a Gmail label (name, visibility)."""
    headers = _auth_header(params)
    payload = {}
    if name is not None:
        payload["name"] = name
    if show_in_label_list is not None:
        payload["labelListVisibility"] = show_in_label_list
    if show_in_message_list is not None:
        payload["messageListVisibility"] = show_in_message_list

    resp = http.patch(f"{BASE_URL}/labels/{id}", json=payload, **http.headers(accept="json", extra=headers))
    return resp["json"]


def delete_label(*, id, **params):
    """Delete a Gmail label (does not delete emails, just removes the label)."""
    headers = _auth_header(params)
    resp = http.delete(f"{BASE_URL}/labels/{id}", **http.headers(accept="json", extra=headers))
    return {"status": "deleted"}


def create_filter(*, from_addr=None, to=None, subject=None, query=None,
                  has_attachment=False, add_labels=None, remove_labels=None,
                  forward_to=None, **params):
    """Create a server-side email filter/rule."""
    headers = _auth_header(params)
    criteria = {}
    if from_addr:
        criteria["from"] = from_addr
    if to:
        criteria["to"] = to
    if subject:
        criteria["subject"] = subject
    if query:
        criteria["query"] = query
    if has_attachment:
        criteria["hasAttachment"] = True

    action = {
        "addLabelIds": add_labels or [],
        "removeLabelIds": remove_labels or [],
    }
    if forward_to:
        action["forward"] = forward_to

    payload = {"criteria": criteria, "action": action}
    resp = http.post(f"{BASE_URL}/settings/filters", json=payload, **http.headers(accept="json", extra=headers))
    return resp["json"]


def delete_filter(*, id, **params):
    """Delete a server-side email filter/rule."""
    headers = _auth_header(params)
    resp = http.delete(f"{BASE_URL}/settings/filters/{id}", **http.headers(accept="json", extra=headers))
    return {"status": "deleted"}
