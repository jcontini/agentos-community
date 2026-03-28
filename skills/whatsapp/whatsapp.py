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
# Person operations
# ==============================================================================


def op_list_persons(*, conversation_id=None, limit=200, **params):
    """Get WhatsApp contacts, or group participants when conversation_id is provided."""
    return sql.query("""
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
        "conversation_id": conversation_id or "",
        "limit": limit,
    }, attach={
        "contacts": CONTACTS_DB,
    })


# ==============================================================================
# Conversation operations
# ==============================================================================


def op_list_conversations(*, archived=False, limit=200, **params):
    """List WhatsApp conversations. Defaults to active (non-archived) chats only."""
    return sql.query("""
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
    return rows[0] if rows else None


# ==============================================================================
# Message operations
# ==============================================================================


def op_list_messages(*, conversation_id=None, is_unread=None, limit=200, **params):
    """List messages in a conversation. Use is_unread=True without conversation_id to get all unread."""
    return sql.query("""
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
        "conversation_id": conversation_id or "",
        "unread": 1 if is_unread else 0,
        "limit": limit,
    })


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
    return rows[0] if rows else None


def op_search_messages(*, query, limit=200, **params):
    """Search messages by text content."""
    return sql.query("""
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
