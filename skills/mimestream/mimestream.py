"""Mimestream skill — local email via SQLite + keychain OAuth.

Reads Mimestream's Core Data store directly. All timestamps are adjusted
by 978307200 seconds (Apple's Core Data epoch: 2001-01-01).

All public functions use keyword-only args and accept **params for
forward-compatibility with engine-injected context.
"""

from agentos import sql, oauth
from agentos.macos import keychain, plist

DB_PATH = "~/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Mimestream.sqlite"


# ==============================================================================
# Shape mapping
# ==============================================================================


def _map_email(row):
    """Map a SQL row to the email shape."""
    result = {
        "id": row["id"],
        "name": row.get("subject"),
        "subject": row.get("subject"),
        "text": row.get("snippet"),
        "author": row.get("from_email"),
        "datePublished": row.get("date_received"),
        "is_unread": bool(row.get("is_unread")),
        "is_starred": bool(row.get("is_flagged")),
        "is_draft": bool(row.get("is_draft")),
        "is_sent": bool(row.get("is_sent")),
        "is_trash": bool(row.get("is_trash")),
        "is_spam": bool(row.get("is_spam")),
        "has_attachments": bool(row.get("has_attachments")),
        "conversation_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "account_email": row.get("account_email"),
    }

    # Optional fields (only on get_email, not list)
    if row.get("message_id"):
        result["message_id"] = row["message_id"]
    if row.get("in_reply_to"):
        result["in_reply_to"] = row["in_reply_to"]
    if row.get("body_text"):
        result["content"] = row["body_text"]
    if row.get("body_html"):
        result["body_html"] = row["body_html"]
    if row.get("size_estimate"):
        result["size_estimate"] = row["size_estimate"]
    if row.get("to_raw"):
        result["to_raw"] = row["to_raw"]
    if row.get("cc_raw"):
        result["cc_raw"] = row["cc_raw"]
    if row.get("bcc_raw"):
        result["bcc_raw"] = row["bcc_raw"]

    # From as typed ref
    from_email = row.get("from_email")
    if from_email:
        acct = {"handle": from_email, "platform": "email"}
        from_name = row.get("from_name")
        if from_name:
            acct["display_name"] = from_name
        result["from"] = {"account": acct}

    return result


def _map_conversation(row):
    """Map a SQL row to the conversation shape."""
    return {
        "id": str(row["id"]),
        "name": row.get("subject"),
        "text": row.get("snippet"),
        "datePublished": row.get("date_updated"),
        "account_email": row.get("account_email"),
    }


# ==============================================================================
# Email operations
# ==============================================================================


def list_emails(*, account=None, mailbox=None, is_unread=None, limit=1000, **params):
    """List emails, optionally filtered by mailbox, account, or flags."""
    rows = sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZSUBJECT as subject,
          m.ZSNIPPET as snippet,
          datetime(m.ZDATERECEIVED + 978307200, 'unixepoch') as date_received,
          datetime(m.ZDATESENT + 978307200, 'unixepoch') as date_sent,
          m.ZISUNREAD as is_unread,
          m.ZISFLAGGED as is_flagged,
          m.ZISDRAFT as is_draft,
          m.ZISSENT as is_sent,
          m.ZISTRASHED as is_trash,
          m.ZISSPAM as is_spam,
          m.ZHASATTACHMENT as has_attachments,
          t.Z_PK as thread_id,
          a.ZNAME as account_email,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(substr(m.ZFROMHEADER, 1, instr(m.ZFROMHEADER, '<') - 1), ' "')
            ELSE NULL
          END as from_name,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(replace(substr(m.ZFROMHEADER, instr(m.ZFROMHEADER, '<') + 1), '>', ''))
            ELSE trim(m.ZFROMHEADER)
          END as from_email
        FROM ZMESSAGE m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        LEFT JOIN ZMESSAGETHREAD t ON m.ZTHREAD = t.Z_PK
        WHERE m.ZISTRASHED = 0
          AND m.ZISSPAM = 0
          AND (:account IS NULL OR a.ZNAME = :account)
          AND (:is_unread IS NULL OR m.ZISUNREAD = :is_unread)
          AND (:mailbox IS NULL OR (
            (:mailbox = 'inbox' AND m.ZISININBOX = 1) OR
            (:mailbox = 'sent' AND m.ZISSENT = 1) OR
            (:mailbox = 'drafts' AND m.ZISDRAFT = 1) OR
            (:mailbox = 'trash' AND m.ZISTRASHED = 1) OR
            (:mailbox = 'spam' AND m.ZISSPAM = 1) OR
            (:mailbox = 'flagged' AND m.ZISFLAGGED = 1)
          ))
        ORDER BY m.ZDATERECEIVED DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "account": account,
        "is_unread": 1 if is_unread is True else (0 if is_unread is False else None),
        "mailbox": mailbox,
        "limit": limit,
    })
    return [_map_email(r) for r in rows]


def get_email(*, id, **params):
    """Get a specific email with full body content and headers."""
    rows = sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZSUBJECT as subject,
          m.ZSNIPPET as snippet,
          datetime(m.ZDATERECEIVED + 978307200, 'unixepoch') as date_received,
          datetime(m.ZDATESENT + 978307200, 'unixepoch') as date_sent,
          m.ZISUNREAD as is_unread,
          m.ZISFLAGGED as is_flagged,
          m.ZISDRAFT as is_draft,
          m.ZISSENT as is_sent,
          m.ZISTRASHED as is_trash,
          m.ZISSPAM as is_spam,
          m.ZHASATTACHMENT as has_attachments,
          m.ZSIZEESTIMATE as size_estimate,
          t.Z_PK as thread_id,
          a.ZNAME as account_email,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(substr(m.ZFROMHEADER, 1, instr(m.ZFROMHEADER, '<') - 1), ' "')
            ELSE NULL
          END as from_name,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(replace(substr(m.ZFROMHEADER, instr(m.ZFROMHEADER, '<') + 1), '>', ''))
            ELSE trim(m.ZFROMHEADER)
          END as from_email,
          c.ZTO as to_raw,
          c.ZCC as cc_raw,
          c.ZBCC as bcc_raw,
          c.ZBODYTEXT as body_text,
          c.ZBODYHTML as body_html,
          c.ZMESSAGEID as message_id,
          c.ZINREPLYTO as in_reply_to
        FROM ZMESSAGE m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        LEFT JOIN ZMESSAGETHREAD t ON m.ZTHREAD = t.Z_PK
        LEFT JOIN ZMESSAGECONTENT c ON m.ZCONTENT = c.Z_PK
        WHERE m.Z_PK = :id
    """, db=DB_PATH, params={"id": id})
    return _map_email(rows[0]) if rows else None


def search_emails(*, query, account=None, limit=1000, **params):
    """Search emails by subject, snippet, body text, or sender."""
    rows = sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZSUBJECT as subject,
          m.ZSNIPPET as snippet,
          datetime(m.ZDATERECEIVED + 978307200, 'unixepoch') as date_received,
          m.ZISUNREAD as is_unread,
          m.ZISFLAGGED as is_flagged,
          m.ZHASATTACHMENT as has_attachments,
          t.Z_PK as thread_id,
          a.ZNAME as account_email,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(substr(m.ZFROMHEADER, 1, instr(m.ZFROMHEADER, '<') - 1), ' "')
            ELSE NULL
          END as from_name,
          CASE
            WHEN instr(m.ZFROMHEADER, '<') > 0
            THEN trim(replace(substr(m.ZFROMHEADER, instr(m.ZFROMHEADER, '<') + 1), '>', ''))
            ELSE trim(m.ZFROMHEADER)
          END as from_email
        FROM ZMESSAGE m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        LEFT JOIN ZMESSAGETHREAD t ON m.ZTHREAD = t.Z_PK
        LEFT JOIN ZMESSAGECONTENT c ON m.ZCONTENT = c.Z_PK
        WHERE m.ZISTRASHED = 0
          AND m.ZISSPAM = 0
          AND (:account IS NULL OR a.ZNAME = :account)
          AND (
            m.ZSUBJECT LIKE '%' || :query || '%'
            OR m.ZSNIPPET LIKE '%' || :query || '%'
            OR c.ZBODYTEXT LIKE '%' || :query || '%'
            OR m.ZFROMHEADER LIKE '%' || :query || '%'
            OR c.ZTO LIKE '%' || :query || '%'
          )
        ORDER BY m.ZDATERECEIVED DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "query": query,
        "account": account,
        "limit": limit,
    })
    return [_map_email(r) for r in rows]


# ==============================================================================
# Conversation operations
# ==============================================================================


def list_conversations(*, account=None, limit=1000, **params):
    """List email threads with latest message info."""
    rows = sql.query("""
        SELECT
          t.Z_PK as id,
          a.ZNAME as account_email,
          (SELECT ZSUBJECT FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as subject,
          (SELECT ZSNIPPET FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as snippet,
          (SELECT datetime(ZDATERECEIVED + 978307200, 'unixepoch') FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as date_updated,
          (SELECT COUNT(*) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as message_count,
          (SELECT MAX(ZISUNREAD) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as has_unread,
          t.ZHASATTACHMENT as has_attachments
        FROM ZMESSAGETHREAD t
        LEFT JOIN ZACCOUNT a ON t.ZACCOUNT = a.Z_PK
        WHERE (:account IS NULL OR a.ZNAME = :account)
        ORDER BY date_updated DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "account": account,
        "limit": limit,
    })
    return [_map_conversation(r) for r in rows]


def get_conversation(*, id, **params):
    """Get all messages in an email thread."""
    rows = sql.query("""
        SELECT
          t.Z_PK as id,
          a.ZNAME as account_email,
          (SELECT ZSUBJECT FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED ASC LIMIT 1) as subject,
          (SELECT ZSNIPPET FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as snippet,
          (SELECT datetime(ZDATERECEIVED + 978307200, 'unixepoch') FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK ORDER BY ZDATERECEIVED DESC LIMIT 1) as date_updated,
          (SELECT COUNT(*) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as message_count,
          (SELECT MAX(ZISUNREAD) FROM ZMESSAGE WHERE ZTHREAD = t.Z_PK) as has_unread,
          t.ZHASATTACHMENT as has_attachments
        FROM ZMESSAGETHREAD t
        LEFT JOIN ZACCOUNT a ON t.ZACCOUNT = a.Z_PK
        WHERE t.Z_PK = :id
    """, db=DB_PATH, params={"id": id})
    return _map_conversation(rows[0]) if rows else None


# ==============================================================================
# Mailbox & account operations
# ==============================================================================


def list_mailboxes(*, account=None, **params):
    """List mailboxes/labels for an account."""
    return sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZNAME as name,
          m.ZROLE as role,
          m.ZUNREADMESSAGECOUNT as unread_count,
          m.ZTOTALMESSAGECOUNT as total_count,
          m.ZTAGBACKGROUNDCOLOR as color,
          a.Z_PK as account_id,
          a.ZNAME as account_email
        FROM ZMAILBOX m
        LEFT JOIN ZACCOUNT a ON m.ZACCOUNT = a.Z_PK
        WHERE m.ZROLE IS NOT NULL
          AND (:account IS NULL OR a.ZNAME = :account)
        ORDER BY
          a.ZDISPLAYORDER,
          CASE m.ZROLE
            WHEN 'INBOX' THEN 1
            WHEN 'INBOX_PRIMARY' THEN 2
            WHEN 'DRAFT' THEN 3
            WHEN 'SENT' THEN 4
            WHEN 'IMPORTANT' THEN 5
            WHEN 'TRASH' THEN 6
            WHEN 'SPAM' THEN 7
            ELSE 10
          END
    """, db=DB_PATH, params={"account": account})


def list_accounts(**params):
    """List configured email accounts with their primary email address."""
    return sql.query("""
        SELECT
          a.Z_PK as id,
          a.ZNAME as name,
          i.ZADDRESS as email,
          a.ZCOLOR as color
        FROM ZACCOUNT a
        LEFT JOIN ZIDENTITY i ON i.ZACCOUNT = a.Z_PK AND i.ZPRIMARY = 1
        ORDER BY a.ZDISPLAYORDER
    """, db=DB_PATH)


# ==============================================================================
# Credential (OAuth token) operation
# ==============================================================================


def credential_get(*, account, **params):
    """Get a live Google OAuth access token from Mimestream's keychain.

    Reads the NSKeyedArchiver binary plist, extracts the refresh token and
    client ID, then exchanges for a fresh access token.
    """
    # Step 1: Read binary plist hex from keychain
    hex_data = keychain.read(
        service=f"Mimestream: {account}",
        account="OAuth",
        binary=True,
    )

    # Step 2: Parse plist — extract fields by $objects index
    fields = plist.parse(hex_data, extract={
        "refresh_token": 32,
        "client_id": 13,
        "token_url": 10,
    })

    # Step 3: Exchange refresh token for access token
    # The response includes "scope" — a space-separated list of granted scopes.
    # Mimestream's Google grant typically includes:
    #   mail.google.com, calendar.events, contacts, contacts.other.readonly,
    #   directory.readonly, gmail.settings.basic, userinfo.profile
    token_response = oauth.exchange(
        token_url=fields["token_url"],
        refresh_token=fields["refresh_token"],
        client_id=fields["client_id"],
    )

    return {
        "access_token": token_response.get("access_token"),
        "expires_in": token_response.get("expires_in"),
        "scope": token_response.get("scope"),
        "refresh_token": fields["refresh_token"],
        "client_id": fields["client_id"],
        "token_url": fields["token_url"],
    }
