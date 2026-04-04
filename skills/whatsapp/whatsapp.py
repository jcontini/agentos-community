"""WhatsApp skill — read WhatsApp messages from local macOS SQLite database.

Reads ~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite
directly. Timestamps are adjusted by 978307200 seconds (Apple's Core Data epoch).

The list_persons operation uses ATTACH to cross-join with the ContactsV2 database
for richer contact metadata.

All public functions use keyword-only args and accept **params for
forward-compatibility with engine-injected context.
"""

from agentos import sql

DB_PATH = "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"
CONTACTS_DB = "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ContactsV2.sqlite"


# ==============================================================================
# Shape mapping
# ==============================================================================


def _jid_to_phone(jid):
    """Convert a WhatsApp JID to a phone number: '1234@s.whatsapp.net' → '+1234'."""
    if not jid or not isinstance(jid, str):
        return None
    if jid.endswith("@s.whatsapp.net"):
        num = jid.split("@")[0]
        return f"+{num}" if not num.startswith("+") else num
    return jid


def _jid_to_account(jid, display_name=None):
    """Convert a WhatsApp JID to an account typed ref dict."""
    if not jid:
        return None
    phone = _jid_to_phone(jid)
    acct = {"id": jid, "platform": "whatsapp", "handle": phone or jid}
    if display_name:
        acct["display_name"] = display_name
    return acct


def _map_person(row):
    """Map a SQL row to the person shape."""
    jid = row.get("jid")
    name = (row.get("real_name") or row.get("contact_name")
            or row.get("display_name") or row.get("phone") or jid)
    result = {
        "id": jid,
        "name": name,
        "content": row.get("about"),
        "nickname": row.get("username"),
    }

    phone = row.get("phone") or _jid_to_phone(jid)

    # Profile photo
    if row.get("profile_photo"):
        result["image"] = row["profile_photo"]

    # WhatsApp account as typed ref
    acct = {"id": jid, "platform": "whatsapp"}
    if phone:
        acct["handle"] = phone
    acct["display_name"] = (row.get("real_name") or row.get("contact_name")
                            or row.get("display_name"))
    if row.get("about"):
        acct["bio"] = row["about"]
    result["accounts"] = [acct]

    return result


def _map_conversation(row):
    """Map a SQL row to the conversation shape."""
    result = {
        "id": row["id"],
        "name": row.get("name"),
        "published": row.get("updated_at"),
        "isGroup": row.get("type") == "group",
        "isArchived": bool(row.get("is_archived")),
        "unreadCount": row.get("unread_count"),
    }

    # Participant as typed ref (for direct chats)
    contact_jid = row.get("contact_jid")
    if contact_jid:
        acct = _jid_to_account(contact_jid, row.get("name"))
        if acct:
            result["participant"] = [acct]

    # Optional counts
    if row.get("participant_count") is not None:
        pass  # derivable from participant relation
    if row.get("message_count") is not None:
        pass  # derivable from message relation

    return result


def _map_message(row):
    """Map a SQL row to the message shape."""
    is_outgoing = bool(row.get("is_outgoing"))
    result = {
        "id": row["id"],
        "name": row.get("conversation_name"),
        "content": row.get("content"),
        "published": row.get("timestamp"),
        "conversationId": row.get("conversation_id"),
        "isOutgoing": is_outgoing,
    }

    if is_outgoing:
        result["author"] = "Me"
    else:
        sender_name = row.get("sender_name")
        if sender_name:
            result["author"] = sender_name

        sender_jid = row.get("sender_jid")
        if sender_jid:
            acct = _jid_to_account(sender_jid, sender_name)
            if acct:
                result["from"] = acct

    # Starred
    if row.get("is_starred"):
        result["is_starred"] = True

    # Reply
    if row.get("reply_to_id"):
        result["replies_to"] = {"id": str(row["reply_to_id"])}

    return result


# ==============================================================================
# Person operations
# ==============================================================================


def op_list_persons(*, conversation_id=None, limit=200, **params):
    """Get WhatsApp contacts, or group participants when conversation_id is provided."""
    rows = sql.query("""
        SELECT DISTINCT
          -- Identity
          COALESCE(cs.ZCONTACTJID, gm.ZMEMBERJID) as jid,
          c.ZPHONENUMBER as phone,

          -- Names (priority: push > contact > partner > group member)
          pn.ZPUSHNAME as real_name,
          c.ZFULLNAME as contact_name,
          COALESCE(cs.ZPARTNERNAME, gm.ZCONTACTNAME, gm.ZFIRSTNAME) as display_name,

          -- Rich data
          c.ZABOUTTEXT as about,
          c.ZUSERNAME as username,
          pp.ZPATH as profile_photo

        FROM (
          -- Branch 1: contacts from chat sessions (default)
          SELECT ZCONTACTJID, ZPARTNERNAME, NULL as ZMEMBERJID, NULL as ZCONTACTNAME, NULL as ZFIRSTNAME
          FROM ZWACHATSESSION
          WHERE ZSESSIONTYPE = 0
            AND ZREMOVED = 0
            AND ZCONTACTJID IS NOT NULL
            AND (:conversation_id IS NULL OR :conversation_id = '')

          UNION ALL

          -- Branch 2: group participants (when conversation_id provided)
          SELECT gm.ZMEMBERJID, NULL, gm.ZMEMBERJID, gm.ZCONTACTNAME, gm.ZFIRSTNAME
          FROM ZWAGROUPMEMBER gm
          WHERE gm.ZCHATSESSION = :conversation_id
            AND :conversation_id IS NOT NULL AND :conversation_id != ''
        ) combined
        LEFT JOIN ZWACHATSESSION cs ON combined.ZCONTACTJID = cs.ZCONTACTJID AND cs.ZSESSIONTYPE = 0
        LEFT JOIN ZWAGROUPMEMBER gm ON combined.ZMEMBERJID = gm.ZMEMBERJID
        LEFT JOIN contacts.ZWAADDRESSBOOKCONTACT c ON (
          COALESCE(combined.ZCONTACTJID, combined.ZMEMBERJID) = c.ZWHATSAPPID OR
          COALESCE(combined.ZCONTACTJID, combined.ZMEMBERJID) = c.ZLID
        )
        LEFT JOIN ZWAPROFILEPUSHNAME pn ON COALESCE(combined.ZCONTACTJID, combined.ZMEMBERJID) = pn.ZJID
        LEFT JOIN ZWAPROFILEPICTUREITEM pp ON COALESCE(combined.ZCONTACTJID, combined.ZMEMBERJID) = pp.ZJID
        ORDER BY real_name, contact_name, display_name
        LIMIT :limit
    """, db=DB_PATH, params={
        "conversationId": conversation_id or "",
        "limit": limit,
    }, attach={
        "contacts": CONTACTS_DB,
    })
    return [_map_person(r) for r in rows]


# ==============================================================================
# Conversation operations
# ==============================================================================


def op_list_conversations(*, archived=False, limit=200, **params):
    """List WhatsApp conversations. Defaults to active (non-archived) chats only."""
    rows = sql.query("""
        SELECT
          cs.Z_PK as id,
          cs.ZPARTNERNAME as name,
          CASE cs.ZSESSIONTYPE
            WHEN 1 THEN 'group'
            ELSE 'direct'
          END as type,
          cs.ZUNREADCOUNT as unread_count,
          cs.ZARCHIVED as is_archived,
          datetime(cs.ZLASTMESSAGEDATE + 978307200, 'unixepoch') as updated_at,
          cs.ZCONTACTJID as contact_jid
        FROM ZWACHATSESSION cs
        WHERE cs.ZREMOVED = 0
          AND cs.ZSESSIONTYPE IN (0, 1)
          AND cs.ZARCHIVED = :archived
        ORDER BY cs.ZLASTMESSAGEDATE DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "archived": 1 if archived else 0,
        "limit": limit,
    })
    return [_map_conversation(r) for r in rows]


def op_get_conversation(*, id, **params):
    """Get a specific conversation with metadata."""
    rows = sql.query("""
        SELECT
          cs.Z_PK as id,
          cs.ZPARTNERNAME as name,
          CASE cs.ZSESSIONTYPE
            WHEN 1 THEN 'group'
            ELSE 'direct'
          END as type,
          cs.ZUNREADCOUNT as unread_count,
          cs.ZARCHIVED as is_archived,
          datetime(cs.ZLASTMESSAGEDATE + 978307200, 'unixepoch') as updated_at,
          cs.ZCONTACTJID as contact_jid,
          (SELECT COUNT(*) FROM ZWAMESSAGE m WHERE m.ZCHATSESSION = cs.Z_PK) as message_count,
          (SELECT COUNT(*) FROM ZWAGROUPMEMBER gm WHERE gm.ZCHATSESSION = cs.Z_PK) as participant_count
        FROM ZWACHATSESSION cs
        WHERE cs.Z_PK = :id
    """, db=DB_PATH, params={"id": id})
    return _map_conversation(rows[0]) if rows else None


# ==============================================================================
# Message operations
# ==============================================================================


def op_list_messages(*, conversation_id=None, is_unread=None, limit=200, **params):
    """List messages in a conversation. Use is_unread=True without conversation_id to get all unread."""
    rows = sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          m.ZISFROMME as is_outgoing,
          CASE m.ZISFROMME
            WHEN 1 THEN NULL
            ELSE m.ZFROMJID
          END as sender_jid,
          CASE m.ZISFROMME
            WHEN 1 THEN NULL
            ELSE COALESCE(pn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp,
          m.ZSTARRED as is_starred,
          m.ZPARENTMESSAGE as reply_to_id
        FROM ZWAMESSAGE m
        JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
        LEFT JOIN ZWAPROFILEPUSHNAME pn ON m.ZFROMJID = pn.ZJID
        WHERE m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
          AND (
            -- When unread=true: get unread incoming messages (optionally filtered by conversation)
            (:unread = 1 AND cs.ZUNREADCOUNT > 0 AND m.ZISFROMME = 0
              AND (:conversation_id IS NULL OR :conversation_id = ''
                OR m.ZCHATSESSION = :conversation_id
                OR cs.ZCONTACTJID = :conversation_id))
            OR
            -- When unread is not set: require conversation_id (numeric or JID)
            (:unread != 1 AND (m.ZCHATSESSION = :conversation_id OR cs.ZCONTACTJID = :conversation_id))
          )
        ORDER BY m.ZMESSAGEDATE DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "conversationId": conversation_id or "",
        "unread": 1 if is_unread else 0,
        "limit": limit,
    })
    return [_map_message(r) for r in rows]


def op_get_message(*, id, **params):
    """Get a specific message by ID."""
    rows = sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          m.ZISFROMME as is_outgoing,
          CASE m.ZISFROMME
            WHEN 1 THEN NULL
            ELSE m.ZFROMJID
          END as sender_jid,
          CASE m.ZISFROMME
            WHEN 1 THEN NULL
            ELSE COALESCE(pn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp,
          m.ZSTARRED as is_starred,
          m.ZPARENTMESSAGE as reply_to_id
        FROM ZWAMESSAGE m
        LEFT JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
        LEFT JOIN ZWAPROFILEPUSHNAME pn ON m.ZFROMJID = pn.ZJID
        WHERE m.Z_PK = :id
    """, db=DB_PATH, params={"id": id})
    return _map_message(rows[0]) if rows else None


def op_search_messages(*, query, limit=200, **params):
    """Search messages by text content."""
    rows = sql.query("""
        SELECT
          m.Z_PK as id,
          m.ZCHATSESSION as conversation_id,
          cs.ZPARTNERNAME as conversation_name,
          m.ZTEXT as content,
          m.ZISFROMME as is_outgoing,
          CASE m.ZISFROMME
            WHEN 1 THEN NULL
            ELSE m.ZFROMJID
          END as sender_jid,
          CASE m.ZISFROMME
            WHEN 1 THEN NULL
            ELSE COALESCE(pn.ZPUSHNAME, cs.ZPARTNERNAME)
          END as sender_name,
          datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as timestamp
        FROM ZWAMESSAGE m
        LEFT JOIN ZWACHATSESSION cs ON m.ZCHATSESSION = cs.Z_PK
        LEFT JOIN ZWAPROFILEPUSHNAME pn ON m.ZFROMJID = pn.ZJID
        WHERE m.ZTEXT LIKE '%' || :query || '%'
        ORDER BY m.ZMESSAGEDATE DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "query": query,
        "limit": limit,
    })
    return [_map_message(r) for r in rows]
