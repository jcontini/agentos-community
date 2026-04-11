"""Mimestream skill — local email via SQLite + keychain OAuth.

Reads Mimestream's Core Data store directly. All timestamps are adjusted
by 978307200 seconds (Apple's Core Data epoch: 2001-01-01).

All public functions use keyword-only args and accept **params for
forward-compatibility with engine-injected context.
"""

from agentos import oauth, sql, returns, provides, oauth_auth
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
        "content": row.get("snippet"),
        "author": row.get("from_email"),
        "published": row.get("date_received"),
        "isUnread": bool(row.get("is_unread")),
        "isStarred": bool(row.get("is_flagged")),
        "isDraft": bool(row.get("is_draft")),
        "isSent": bool(row.get("is_sent")),
        "isTrash": bool(row.get("is_trash")),
        "isSpam": bool(row.get("is_spam")),
        "hasAttachments": bool(row.get("has_attachments")),
        "conversationId": str(row["thread_id"]) if row.get("thread_id") else None,
        "accountEmail": row.get("account_email"),
    }

    # Optional fields (only on get_email, not list)
    if row.get("message_id"):
        result["messageId"] = row["message_id"]
    if row.get("in_reply_to"):
        result["inReplyTo"] = row["in_reply_to"]
    if row.get("body_text"):
        result["content"] = row["body_text"]
    if row.get("body_html"):
        result["bodyHtml"] = row["body_html"]
    if row.get("size_estimate"):
        result["sizeEstimate"] = row["size_estimate"]
    if row.get("to_raw"):
        result["toRaw"] = row["to_raw"]
    if row.get("cc_raw"):
        result["ccRaw"] = row["cc_raw"]
    if row.get("bcc_raw"):
        result["bccRaw"] = row["bcc_raw"]

    # From as typed ref
    from_email = row.get("from_email")
    if from_email:
        acct = {"handle": from_email, "platform": "email"}
        from_name = row.get("from_name")
        if from_name:
            acct["display_name"] = from_name
        result["from"] = acct

    return result


def _map_conversation(row):
    """Map a SQL row to the conversation shape."""
    return {
        "id": str(row["id"]),
        "name": row.get("subject"),
        "content": row.get("snippet"),
        "published": row.get("date_updated"),
        "accountEmail": row.get("account_email"),
    }


# ==============================================================================
# Email operations
# ==============================================================================


@returns("email[]")
async def list_emails(*, account=None, mailbox=None, is_unread=None, limit=1000, **params):
    """List emails, optionally filtered by mailbox, account, or flags."""
    rows = await sql.query("""
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
        "isUnread": 1 if is_unread is True else (0 if is_unread is False else None),
        "mailbox": mailbox,
        "limit": limit,
    })
    return [_map_email(r) for r in rows]


@returns("email")
async def get_email(*, id, **params):
    """Get a specific email with full body content and headers."""
    rows = await sql.query("""
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


@returns("email[]")
async def search_emails(*, query, account=None, limit=1000, **params):
    """Search emails by subject, snippet, body text, or sender."""
    rows = await sql.query("""
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


@returns("conversation[]")
async def list_conversations(*, account=None, limit=1000, **params):
    """List email threads with latest message info."""
    rows = await sql.query("""
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


@returns("conversation")
async def get_conversation(*, id, **params):
    """Get all messages in an email thread."""
    rows = await sql.query("""
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


@returns({"id": "integer", "name": "string", "role": "string", "unreadCount": "integer", "totalCount": "integer", "accountEmail": "string"})
async def list_mailboxes(*, account=None, **params):
    """List mailboxes/labels for an account."""
    return await sql.query("""
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


@returns({"id": "integer", "name": "string", "email": "string", "color": "string"})
async def list_accounts(**params):
    """List configured email accounts with their primary email address."""
    return await sql.query("""
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


@returns({"accessToken": "string", "refreshToken": "string", "clientId": "string", "tokenUrl": "string"})
@provides(oauth_auth, service="google", account_param="account")
async def credential_get(*, account, **params):
    """Get a live Google OAuth access token from Mimestream's keychain.

    Reads the NSKeyedArchiver binary plist, extracts the refresh token and
    client ID, then exchanges for a fresh access token.
    """
    # Step 1: Read binary plist hex from keychain
    hex_data = await keychain.read(
        service=f"Mimestream: {account}",
        account="OAuth",
        binary=True,
    )

    # Step 2: Parse plist — extract fields by $objects index
    fields = await plist.parse(hex_data, extract={
        "refreshToken": 32,
        "clientId": 13,
        "tokenUrl": 10,
    })

    # Step 3: Exchange refresh token for access token
    # The response includes "scope" — a space-separated list of granted scopes.
    # Mimestream's Google grant typically includes:
    #   mail.google.com, calendar.events, contacts, contacts.other.readonly,
    #   directory.readonly, gmail.settings.basic, userinfo.profile
    token_response = await oauth.exchange(
        token_url=fields["token_url"],
        refresh_token=fields["refresh_token"],
        client_id=fields["client_id"],
    )

    return {
        "accessToken": token_response.get("access_token"),
        "expiresIn": token_response.get("expires_in"),
        "scope": token_response.get("scope"),
        "refreshToken": fields["refresh_token"],
        "clientId": fields["client_id"],
        "tokenUrl": fields["token_url"],
    }
