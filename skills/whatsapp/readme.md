---
id: whatsapp
name: WhatsApp
description: Read WhatsApp messages from local macOS database
icon: icon.svg
color: "#2CD46B"

website: https://www.whatsapp.com/

connections: {}

database: "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"
# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  person:
    id: .jid
    name: '.real_name // .contact_name // .display_name // .phone // .jid'
    text: .about
    phone: '.phone // (if (.jid | type == "string" and endswith("@s.whatsapp.net")) then (.jid | split("@") | .[0] | if startswith("+") then . else "+" + . end) else null end)'
    nickname: .username
    notes: .about
    avatar:
      image:
        path: .profile_photo
    claim:
      account:
        id: .jid
        platform: '"whatsapp"'
        handle: '.phone // (if (.jid | type == "string" and endswith("@s.whatsapp.net")) then (.jid | split("@") | .[0] | "+" + .) else .jid end)'
        display_name: '.real_name // .contact_name // .display_name'
        platform_id: .jid
        bio: .about

  conversation:
    id: .id
    name: .name
    datePublished: .updated_at
    is_group: '.type == "group"'
    is_archived: '.is_archived == 1 or .is_archived == true'
    unread_count: .unread_count
    participant_count: .participant_count
    last_message_at: .updated_at
    updated_at: .updated_at
    data.message_count: .message_count
    _contact_jid: .contact_jid
    _contact_name: .name
    participant:
      account:
        id: ._contact_jid
        platform: '"whatsapp"'
        handle: 'if (._contact_jid | type == "string" and endswith("@s.whatsapp.net")) then (._contact_jid | split("@") | .[0] | "+" + .) else ._contact_jid end'
        display_name: ._contact_name

  message:
    id: .id
    name: .conversation_name
    text: .content
    author: 'if .is_outgoing == 1 or .is_outgoing == true then "Me" else .sender_name end'
    datePublished: .timestamp
    conversation_id: .conversation_id
    content: .content
    is_outgoing: '.is_outgoing == 1 or .is_outgoing == true'
    timestamp: .timestamp
    data.is_starred: .is_starred
    data.conversation_name: .conversation_name
    _reply_to_id: .reply_to_id
    _sender_jid: .sender_jid
    _sender_name: .sender_name
    from:
      account:
        id: ._sender_jid
        platform: '"whatsapp"'
        handle: 'if (._sender_jid | type == "string" and endswith("@s.whatsapp.net")) then (._sender_jid | split("@") | .[0] | "+" + .) else ._sender_jid end'
        display_name: ._sender_name

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  list_persons:
    description: Get WhatsApp contacts, or group participants when conversation_id is provided
    returns: person[]
    params:
      conversation_id: { type: string, description: "Group conversation ID — returns participants instead of contacts" }
      limit: { type: integer }
    sql:
      attach:
        contacts: '"~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ContactsV2.sqlite"'
      query: |
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
      params:
        conversation_id: '.params.conversation_id // ""'
        limit: '.params.limit // 1000'
      response:
        root: "/"

  list_conversations:
    description: List WhatsApp conversations. Defaults to active (non-archived) chats only. Use archived=true to list archived conversations instead.
    returns: conversation[]
    params:
      archived: { type: boolean, description: "When true, returns archived conversations. Defaults to false (active chats only)." }
      limit: { type: integer }
    sql:
      query: |
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
      params:
        archived: 'if .params.archived == true then 1 else 0 end'
        limit: '.params.limit // 1000'
      response:
        root: "/"

  get_conversation:
    description: Get a specific conversation with metadata
    returns: conversation
    params:
      id: { type: string, required: true }
    sql:
      query: |
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
      params:
        id: .params.id
      response:
        root: "/0"

  list_messages:
    description: List messages in a conversation. Use unread=true without conversation_id to get all unread messages across conversations.
    returns: message[]
    params:
      conversation_id: { type: string, description: "Conversation ID — numeric (897) or JID (251921615223@s.whatsapp.net). Get from conversation.list." }
      unread: { type: boolean, description: "When true, returns unread incoming messages (conversation_id optional)" }
      limit: { type: integer }
    sql:
      query: |
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
      params:
        conversation_id: '.params.conversation_id // ""'
        unread: 'if .params.unread == true then 1 else 0 end'
        limit: '.params.limit // 1000'
      response:
        root: "/"

  get_message:
    description: Get a specific message by ID
    returns: message
    params:
      id: { type: string, required: true }
    sql:
      query: |
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
      params:
        id: .params.id
      response:
        root: "/0"

  search_messages:
    description: Search messages by text content
    returns: message[]
    params:
      query: { type: string, required: true }
      limit: { type: integer }
    sql:
      query: |
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
      params:
        query: .params.query
        limit: '.params.limit // 1000'
      response:
        root: "/"

---

# WhatsApp

Read WhatsApp messages from the local macOS database. Read-only access to message history.

## Requirements

- **macOS only** — Reads from local WhatsApp database
- **WhatsApp desktop app** — Must be installed and logged in

## Conversation IDs

Conversations use numeric IDs (SQLite primary keys like `880`, `899`). Always use the `id` returned by `list_conversations` — these are **not** JIDs.

## Common Tasks

- **Get active chats:** `list_conversations` (default — non-archived only)
- **Get archived chats:** `list_conversations` with `archived: true`
- **Get unread messages:** `list_messages` with `unread: true` (no conversation_id needed)
- **Get group participants:** `list_persons` with `conversation_id` param
- **Search messages:** `search_messages` with `query` param

## Contact Identifiers

WhatsApp uses two identifier formats:
- **JID:** `12125551234@s.whatsapp.net` (phone-based, used for DMs)
- **LID:** `opaque_id@lid` (server-assigned, newer format)

The `list_persons` operation resolves both formats to phone numbers when available via the contacts database.

## Entity Model

- **person** — the human, with phone number and name from contacts
- **account** — their WhatsApp identity (JID/LID), linked to person via `claim` relationship
- **conversation** — a chat thread, with `participant` → account reference for the DM partner
- **message** — a text message, with `from` → account reference for the sender

This means: person → claims → account → sends → message. Traverse the graph to connect messages to people.

## Notes

- `is_outgoing: true` indicates messages you sent
- Incoming messages include a `from` account reference for the sender's WhatsApp identity
- Media-only messages (images, voice notes) without text are excluded from message queries
- All timestamps are ISO 8601 format
