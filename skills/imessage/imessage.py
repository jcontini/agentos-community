"""iMessage skill — read and send iMessages/SMS via macOS Messages SQLite DB.

Reads ~/Library/Messages/chat.db directly. Timestamps are converted from
Apple's Core Data epoch (nanoseconds since 2001-01-01) to ISO datetime.

All public functions use keyword-only args and accept **params for
forward-compatibility with engine-injected context.
"""

import json

from agentos import shell, sql

DB_PATH = "~/Library/Messages/chat.db"


# ==============================================================================
# Conversation operations
# ==============================================================================


def op_list_conversations(*, limit=200, **params):
    """List all iMessage/SMS conversations."""
    return sql.query("""
        SELECT
          c.ROWID as id,
          COALESCE(c.display_name, c.chat_identifier) as name,
          c.service_name as platform,
          CASE
            WHEN (SELECT COUNT(*) FROM chat_handle_join chj WHERE chj.chat_id = c.ROWID) > 1
            THEN 'group'
            ELSE 'direct'
          END as type,
          datetime(
            (SELECT MAX(m.date) FROM message m
             JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
             WHERE cmj.chat_id = c.ROWID) / 1000000000 + 978307200,
            'unixepoch'
          ) as updated_at,
          (SELECT GROUP_CONCAT(h.id, ',')
           FROM handle h
           JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
           WHERE chj.chat_id = c.ROWID) as participant_handles
        FROM chat c
        WHERE EXISTS (
          SELECT 1 FROM message m
          JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
          WHERE cmj.chat_id = c.ROWID
        )
        ORDER BY updated_at DESC
        LIMIT :limit
    """, db=DB_PATH, params={"limit": limit})


def op_get_conversation(*, id, **params):
    """Get a specific conversation with metadata."""
    rows = sql.query("""
        SELECT
          c.ROWID as id,
          COALESCE(c.display_name, c.chat_identifier) as name,
          c.service_name as platform,
          CASE
            WHEN (SELECT COUNT(*) FROM chat_handle_join chj WHERE chj.chat_id = c.ROWID) > 1
            THEN 'group'
            ELSE 'direct'
          END as type,
          datetime(
            (SELECT MAX(m.date) FROM message m
             JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
             WHERE cmj.chat_id = c.ROWID) / 1000000000 + 978307200,
            'unixepoch'
          ) as updated_at,
          (SELECT GROUP_CONCAT(h.id, ',')
           FROM handle h
           JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
           WHERE chj.chat_id = c.ROWID) as participant_handles
        FROM chat c
        WHERE c.ROWID = :id
    """, db=DB_PATH, params={"id": id})
    return rows[0] if rows else None


# ==============================================================================
# Message operations
# ==============================================================================


def op_list_messages(*, conversation_id, limit=200, **params):
    """List messages in a conversation."""
    return sql.query("""
        SELECT
          m.ROWID as id,
          :conversation_id as conversation_id,
          m.text as content,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me
            WHEN 1 THEN NULL
            ELSE h.id
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        WHERE cmj.chat_id = :conversation_id
          AND m.text IS NOT NULL AND m.text != ''
        ORDER BY m.date DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "conversation_id": conversation_id,
        "limit": limit,
    })


def op_get_message(*, id, **params):
    """Get a specific message by ID."""
    rows = sql.query("""
        SELECT
          m.ROWID as id,
          c.ROWID as conversation_id,
          m.text as content,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me
            WHEN 1 THEN NULL
            ELSE h.id
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.ROWID = :id
    """, db=DB_PATH, params={"id": id})
    return rows[0] if rows else None


def op_search_messages(*, query, limit=200, **params):
    """Search messages by text content."""
    return sql.query("""
        SELECT
          m.ROWID as id,
          c.ROWID as conversation_id,
          COALESCE(c.display_name, c.chat_identifier) as conversation_name,
          m.text as content,
          m.is_from_me as is_outgoing,
          CASE m.is_from_me
            WHEN 1 THEN 'Me'
            ELSE COALESCE(h.id, 'Unknown')
          END as sender_handle,
          datetime(m.date / 1000000000 + 978307200, 'unixepoch') as timestamp
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
        LEFT JOIN chat c ON cmj.chat_id = c.ROWID
        WHERE m.text LIKE '%' || :query || '%'
        ORDER BY m.date DESC
        LIMIT :limit
    """, db=DB_PATH, params={
        "query": query,
        "limit": limit,
    })


# ==============================================================================
# Send operation
# ==============================================================================


def op_send_message(*, to, text, service="iMessage", **params):
    """Send an iMessage or SMS to a phone number or email."""
    result = shell.run("imsg", ["send", "--to", to, "--text", text, "--service", service, "--json"], timeout=15)
    if result["exit_code"] != 0:
        raise RuntimeError(f"imsg send failed: {result['stderr'].strip()}")
    return json.loads(result["stdout"]) if result["stdout"].strip() else None
