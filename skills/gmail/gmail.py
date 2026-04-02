"""Gmail skill — all operations implemented via http.get()/http.post()/etc.

All public functions take **params. Auth token lives in
params["auth"]["access_token"], injected by the engine from OAuth resolution.
"""

import base64
import json
import re
import time
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


def _decode_body_html(payload):
    """Find the text/html part and base64url-decode its content."""
    if not payload:
        return ""

    def _find_html(part):
        mime = part.get("mimeType", "")
        if mime == "text/html":
            data = (part.get("body") or {}).get("data", "")
            if data:
                padded = data + "=" * ((4 - len(data) % 4) % 4)
                try:
                    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
                except Exception:
                    return ""
        if mime.startswith("multipart/"):
            for sub in part.get("parts") or []:
                result = _find_html(sub)
                if result:
                    return result
        return ""

    for sub in payload.get("parts") or []:
        result = _find_html(sub)
        if result:
            return result
    return _find_html(payload)


def _extract_manage_subscription_url(html):
    """Extract manage subscription/preferences URL from HTML using lxml.

    Looks for links by href patterns and anchor text patterns,
    language-independent where possible.
    """
    if not html:
        return None
    try:
        from lxml import html as lxml_html
    except ImportError:
        return None

    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return None

    # Strategy 1: href patterns — these are URL-based, language-independent
    href_patterns = [
        "manage_subscription", "manage-subscription",
        "manage_preferences", "manage-preferences",
        "subscription_preferences", "subscription-preferences",
        "email_preferences", "email-preferences",
        "communication_preferences", "communication-preferences",
        "notification_preferences", "notification-preferences",
        "update_preferences", "update-preferences",
        "mailing_preferences", "mailing-preferences",
        "list-manage.com/profile",     # Mailchimp
        "manage_subscription_preferences",  # Customer.io
        "email-preferences",           # HubSpot
        "subscription-center",         # Salesforce
        "preference-center",           # Generic
    ]
    for link in doc.cssselect("a[href]"):
        href = link.get("href", "")
        href_lower = href.lower()
        for pattern in href_patterns:
            if pattern in href_lower:
                return href

    # Strategy 2: anchor text (English fallback)
    text_patterns = [
        "manage preferences", "update preferences",
        "manage your preferences", "update your preferences",
        "email preferences", "subscription preferences",
        "communication preferences", "notification preferences",
        "manage subscription", "manage your subscription",
    ]
    for link in doc.cssselect("a[href]"):
        text = (link.text_content() or "").strip().lower()
        for pattern in text_patterns:
            if pattern in text:
                return link.get("href", "")

    return None


def _collect_attachments(payload):
    """Recursively collect attachment metadata as file-shaped objects."""
    results = []
    if not payload:
        return results

    def _mime_to_format(mime_type):
        """Derive human-readable format from MIME type."""
        formats = {
            "application/pdf": "PDF",
            "application/zip": "ZIP",
            "application/gzip": "GZIP",
            "text/plain": "TXT",
            "text/csv": "CSV",
            "text/html": "HTML",
            "image/png": "PNG",
            "image/jpeg": "JPEG",
            "image/gif": "GIF",
            "image/webp": "WebP",
        }
        if not mime_type:
            return None
        return formats.get(mime_type)

    def _walk(part):
        filename = part.get("filename")
        body = part.get("body") or {}
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            mime_type = part.get("mimeType")
            results.append(
                {
                    "id": attachment_id,
                    "name": filename,
                    "filename": filename,
                    "mime_type": mime_type,
                    "format": _mime_to_format(mime_type),
                    "size": body.get("size"),
                    "encoding": "base64url",
                }
            )
        for sub in part.get("parts") or []:
            _walk(sub)

    _walk(payload)
    return results


def _extract_domain(email_addr):
    """Extract domain from an email address."""
    if not email_addr or "@" not in email_addr:
        return None
    return email_addr.rsplit("@", 1)[1].lower()


def _domains_from_accounts(accounts):
    """Extract unique domain objects from a list of parsed account dicts."""
    seen = set()
    domains = []
    for acct in accounts:
        domain = _extract_domain(acct.get("handle", ""))
        if domain and domain not in seen:
            seen.add(domain)
            domains.append({"name": domain})
    return domains


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

    to_accounts = _parse_addresses(_get_header(headers, "To"))
    cc_accounts = _parse_addresses(_get_header(headers, "Cc"))
    bcc_accounts = _parse_addresses(_get_header(headers, "Bcc"))
    attachments = _collect_attachments(payload)

    # Extract List-Unsubscribe header (RFC 2369) — prefer URL over mailto
    # RFC 8058: List-Unsubscribe-Post enables one-click unsubscribe via POST
    unsubscribe = None
    unsubscribe_one_click = False
    unsub_raw = _get_header(headers, "List-Unsubscribe") or ""
    if unsub_raw:
        urls = re.findall(r"<([^>]+)>", unsub_raw)
        for url in urls:
            if url.startswith("http"):
                unsubscribe = url
                break
        if not unsubscribe and urls:
            unsubscribe = urls[0]
    if _get_header(headers, "List-Unsubscribe-Post") and unsubscribe and unsubscribe.startswith("http"):
        unsubscribe_one_click = True

    # List-Id (RFC 2919) — extract the identifier from angle brackets
    list_id_raw = _get_header(headers, "List-Id") or ""
    list_id_match = re.search(r"<([^>]+)>", list_id_raw)
    list_id = list_id_match.group(1) if list_id_match else (list_id_raw.strip() or None)

    # Auto-Submitted (RFC 3834) — anything other than "no" means automated
    auto_submitted = _get_header(headers, "Auto-Submitted")
    is_automated = auto_submitted is not None and auto_submitted.lower() != "no"

    # Manage subscription URL — look for List-Subscribe header first,
    # then scan body for common preference center patterns
    manage_sub = None
    list_subscribe_raw = _get_header(headers, "List-Subscribe") or ""
    if list_subscribe_raw:
        sub_urls = re.findall(r"<([^>]+)>", list_subscribe_raw)
        for url in sub_urls:
            if url.startswith("http"):
                manage_sub = url
                break
    if not manage_sub:
        # Parse HTML body with lxml — href patterns are language-independent
        body_html = _decode_body_html(payload)
        manage_sub = _extract_manage_subscription_url(body_html)

    return {
        "id": msg.get("id"),
        "name": subject,
        "text": msg.get("snippet", ""),
        "author": author,
        "datePublished": _internaldate_to_iso(msg.get("internalDate")),
        "is_starred": "STARRED" in label_ids,
        "is_unread": "UNREAD" in label_ids,
        "is_draft": "DRAFT" in label_ids,
        "is_sent": "SENT" in label_ids,
        "is_trash": "TRASH" in label_ids,
        "is_spam": "SPAM" in label_ids,
        "is_automated": is_automated,
        "has_attachments": len(attachments) > 0,
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
        "return_path": _get_header(headers, "Return-Path"),
        "list_id": list_id,
        "precedence": _get_header(headers, "Precedence"),
        "mailer": _get_header(headers, "X-Mailer") or _get_header(headers, "User-Agent"),
        "auth_results": _get_header(headers, "Authentication-Results"),
        "feedback_id": _get_header(headers, "Feedback-ID"),
        "unsubscribe": unsubscribe,
        "unsubscribe_one_click": unsubscribe_one_click,
        "manage_subscription": manage_sub,
        "attachments": attachments,
        # Relations
        "from": from_obj,
        "to": to_accounts,
        "cc": cc_accounts,
        "bcc": bcc_accounts,
        "domain": {"name": _extract_domain(from_obj.get("handle", ""))} if _extract_domain(from_obj.get("handle", "")) else None,
        "to_domain": _domains_from_accounts(to_accounts),
        "cc_domain": _domains_from_accounts(cc_accounts),
    }


def _map_conversation(thread):
    """Map a Gmail thread object to the agentOS conversation shape."""
    if not thread:
        return thread
    raw_messages = thread.get("messages") or []
    snippet = thread.get("snippet", "")

    # Subject from first message
    name = None
    if raw_messages:
        first_headers = (raw_messages[0].get("payload") or {}).get("headers") or []
        name = _get_header(first_headers, "Subject")
    if not name:
        name = snippet[:120] + ("…" if len(snippet) > 120 else "")

    # datePublished from last message
    date_published = None
    if raw_messages:
        date_published = _internaldate_to_iso(raw_messages[-1].get("internalDate"))

    # Map messages through _map_email and extract unique participants
    mapped_messages = [_map_email(m) for m in raw_messages] if raw_messages else []
    participants = _extract_participants(mapped_messages)

    # Unread if any message is unread
    unread_count = sum(1 for m in mapped_messages if m and m.get("is_unread"))

    return {
        "id": thread.get("id"),
        "name": name,
        "text": snippet,
        "datePublished": date_published,
        "message_count": len(mapped_messages) if mapped_messages else None,
        "unread_count": unread_count,
        "history_id": thread.get("historyId"),
        # Relations
        "message": mapped_messages,
        "participant": participants,
    }


def _extract_participants(mapped_emails):
    """Extract unique participant accounts from a list of mapped emails."""
    seen = set()
    participants = []
    for email in mapped_emails:
        if not email:
            continue
        # Collect from, to, cc, bcc
        accounts = []
        from_obj = email.get("from")
        if from_obj:
            accounts.append(from_obj)
        accounts.extend(email.get("to") or [])
        accounts.extend(email.get("cc") or [])
        accounts.extend(email.get("bcc") or [])
        for acct in accounts:
            handle = acct.get("handle", "")
            if handle and handle not in seen:
                seen.add(handle)
                participants.append(acct)
    return participants


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


def _map_label(label):
    """Map a Gmail label to the tag shape."""
    return {
        "id": label.get("id"),
        "name": label.get("name"),
        "tag_type": label.get("type", "").lower() or None,  # system, user
        "color": (label.get("color") or {}).get("backgroundColor"),
    }


def list_labels(**params):
    """List all Gmail labels (system and user-created) as tags."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/labels", **http.headers(accept="json", extra=headers))
    return [_map_label(l) for l in resp["json"].get("labels", [])]


def get_attachment(*, message_id, attachment_id, **params):
    """Download an email attachment as a file with base64url-encoded content."""
    headers = _auth_header(params)
    resp = http.get(
        f"{BASE_URL}/messages/{message_id}/attachments/{attachment_id}",
        **http.headers(accept="json", extra=headers),
    )
    data = resp["json"]
    return {
        "id": attachment_id,
        "name": attachment_id,
        "content": data.get("data", ""),
        "size": data.get("size"),
        "encoding": "base64url",
    }


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
    """List drafts with full email content — fetches stubs then hydrates each via get_draft."""
    headers = _auth_header(params)
    query_params = {"maxResults": str(limit)}
    if query:
        query_params["q"] = query
    if page_token:
        query_params["pageToken"] = page_token

    resp = http.get(f"{BASE_URL}/drafts", params=query_params, **http.headers(accept="json", extra=headers))
    stubs = resp["json"].get("drafts", [])
    if not stubs:
        return []
    return [get_draft(id=s["id"], **params) for s in stubs]


def get_draft(*, id, **params):
    """Get a draft with full message content, mapped to the email shape."""
    headers = _auth_header(params)
    resp = http.get(f"{BASE_URL}/drafts/{id}", params={"format": "full"}, **http.headers(accept="json", extra=headers))
    draft = resp["json"]
    email = _map_email(draft.get("message", {}))
    if email:
        email["draft_id"] = draft.get("id")
    return email


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
# Unsubscribe (RFC 8058 one-click)
# ==============================================================================


def unsubscribe_email(*, id, **params):
    """Unsubscribe from a mailing list using RFC 8058 one-click.

    Fetches the email, checks for List-Unsubscribe + List-Unsubscribe-Post
    headers, and fires the POST. No browser or cookies needed.
    """
    email = get_email(id=id, **params)
    if not email:
        raise ValueError("Email not found")

    unsub_url = email.get("unsubscribe")
    one_click = email.get("unsubscribe_one_click")

    if not unsub_url:
        raise ValueError(
            f"No List-Unsubscribe header on this email (from: {email.get('author') or email.get('from', {}).get('handle')}). "
            f"Manual unsubscribe may be required — check the email body for a link."
        )

    if not one_click:
        return {
            "status": "manual_required",
            "unsubscribe_url": unsub_url,
            "message": "This sender doesn't support one-click unsubscribe. Open this URL in a browser to unsubscribe.",
        }

    # RFC 8058: POST with form data List-Unsubscribe=One-Click
    resp = http.post(unsub_url, data={"List-Unsubscribe": "One-Click"})
    status_code = resp.get("status", 0)

    return {
        "status": "unsubscribed" if 200 <= status_code < 300 else "failed",
        "status_code": status_code,
        "from": email.get("from", {}).get("handle"),
        "domain": (email.get("domain") or {}).get("name"),
        "subject": email.get("name"),
        "thread_id": email.get("conversation_id"),
        "message_id": email.get("message_id"),
    }


# ==============================================================================
# Gmail sync protocol (cookie-authenticated)
# ==============================================================================

# Gmail's internal label identifiers for unsubscribe state.
# Discovered via CDP capture of Gmail's web UI unsubscribe flow.
_CATEGORY_TO_SMARTLABEL = {
    "CATEGORY_PROMOTIONS": "^smartlabel_promo",
    "CATEGORY_UPDATES": "^smartlabel_notification",
    "CATEGORY_SOCIAL": "^smartlabel_social",
    "CATEGORY_FORUMS": "^smartlabel_group",
    "CATEGORY_PERSONAL": "^smartlabel_personal",
}

SYNC_BASE = "https://mail.google.com/sync/u/0/i/s"


def sync_unsubscribe(*, msg_id, thread_id, message_id_header="", label_ids=None, **params):
    """Record an unsubscribe in Gmail's internal state via the sync protocol.

    Applies ^punsub (unsubscribed) and ^punsub_sat (satisfied) internal labels
    to a thread. This is exactly what Gmail's web UI does when you click the
    Unsubscribe button — it makes the 'You unsubscribed' banner appear and
    hides the Unsubscribe link on future emails from that sender.

    Uses the 'sync' connection (cookie-auth from browser), not OAuth.
    Call this AFTER unsubscribe_email to complete the full unsubscribe flow.
    """
    from agentos import get_cookies
    cookie_header = get_cookies(params)
    if not cookie_header:
        raise ValueError("No Gmail session cookies available. The 'sync' connection requires browser cookies.")

    thread_ref = f"thread-f:{thread_id}"
    msg_ref = f"msg-f:{msg_id}"

    # Map Gmail label IDs to internal smartlabel refs
    smartlabel_refs = []
    for lid in (label_ids or []):
        if lid in _CATEGORY_TO_SMARTLABEL:
            smartlabel_refs.append(_CATEGORY_TO_SMARTLABEL[lid])

    now_ms = int(time.time() * 1000)
    payload = [
        None,
        [[[99, [thread_ref, [
            None, None, None, None, None, None,
            [
                ["^punsub", "^punsub_sat"],
                None,
                [msg_ref],
                None, None, None, None, None, None, None, None,
                [None, [message_id_header] if message_id_header else [], smartlabel_refs]
            ]
        ]]]]],
        [1, 0, None, None, [None, 0], None, 1],
        [now_ms, 1, now_ms + 100, 0, 47],
        2
    ]

    resp = http.post(
        SYNC_BASE,
        params={"hl": "en", "c": "0", "rt": "r", "pt": "ji"},
        json=payload,
        cookies=cookie_header,
    )

    status_code = resp.get("status", 0)
    if status_code != 200:
        return {"status": "failed", "status_code": status_code}

    return {
        "status": "synced",
        "thread_id": thread_id,
        "labels_applied": ["^punsub", "^punsub_sat"],
    }


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
    draft = resp["json"]
    email = _map_email(draft.get("message", {}))
    if email:
        email["draft_id"] = draft.get("id")
    return email


def update_draft(*, id, to, subject, body, html_body=None, cc=None, bcc=None, **params):
    """Update an existing draft."""
    raw = _build_raw(to, subject, body, html_body=html_body, cc=cc, bcc=bcc)
    headers = _auth_header(params)
    resp = http.put(
        f"{BASE_URL}/drafts/{id}",
        json={"message": {"raw": raw}},
        **http.headers(accept="json", extra=headers),
    )
    draft = resp["json"]
    email = _map_email(draft.get("message", {}))
    if email:
        email["draft_id"] = draft.get("id")
    return email


def send_draft(*, id, **params):
    """Send an existing draft."""
    headers = _auth_header(params)
    resp = http.post(
        f"{BASE_URL}/drafts/send",
        json={"id": id},
        **http.headers(accept="json", extra=headers),
    )
    return _map_email(resp["json"])


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
    """Create a new Gmail label, returned as a tag."""
    headers = _auth_header(params)
    payload = {
        "name": name,
        "labelListVisibility": show_in_label_list or "labelShow",
        "messageListVisibility": show_in_message_list or "show",
    }
    resp = http.post(f"{BASE_URL}/labels", json=payload, **http.headers(accept="json", extra=headers))
    return _map_label(resp["json"])


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
    return _map_label(resp["json"])


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
