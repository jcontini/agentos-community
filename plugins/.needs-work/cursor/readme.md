---
id: cursor
name: Cursor
description: AI-powered code editor conversation history
icon: icon.png
tags: [AI]

website: https://cursor.sh
# No auth block = no credentials needed (local database)

database:
  macos: "~/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
  windows: "%APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb"
  linux: "~/.config/Cursor/User/globalStorage/state.vscdb"

instructions: |
  Cursor stores AI chat history in a local SQLite database.
  - Conversations are stored as JSON in a key-value table
  - Message type: 1 = user, 2 = assistant
  - Timestamps are Unix milliseconds
  - Code blocks are embedded in markdown content, not separate

# Action implementations (merged from mapping.yaml)
actions:
  list_conversations:
    operation: read
    label: "List conversations"
    description: List all AI chat conversations
    params:
      limit: { type: number, default: 50 }
    sql:
      query: |
        SELECT 
          json_extract(value, '$.composerId') as id,
          json_extract(value, '$.name') as name,
          json_extract(value, '$.createdAt') as created_at,
          datetime(json_extract(value, '$.lastUpdatedAt') / 1000, 'unixepoch') as updated_at,
          json_extract(value, '$.unifiedMode') as mode,
          json_array_length(json_extract(value, '$.fullConversationHeadersOnly')) as message_count
        FROM cursorDiskKV
        WHERE key LIKE 'composerData:%'
          AND json_extract(value, '$.composerId') IS NOT NULL
        ORDER BY json_extract(value, '$.lastUpdatedAt') DESC
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          type: "'ai_chat'"
          name: "[].name"
          created_at: "[].created_at"
          updated_at: "[].updated_at"
          platform: "'cursor'"
          connector: "'cursor'"

  get_conversation:
    operation: read
    label: "Get conversation"
    description: Get a specific conversation with metadata
    params:
      conversation_id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          json_extract(value, '$.composerId') as id,
          json_extract(value, '$.name') as name,
          json_extract(value, '$.createdAt') as created_at,
          datetime(json_extract(value, '$.lastUpdatedAt') / 1000, 'unixepoch') as updated_at,
          json_extract(value, '$.unifiedMode') as mode,
          json_array_length(json_extract(value, '$.fullConversationHeadersOnly')) as message_count
        FROM cursorDiskKV
        WHERE key = 'composerData:{{params.conversation_id}}'
      response:
        mapping:
          id: ".id"
          type: "'ai_chat'"
          name: ".name"
          created_at: ".created_at"
          updated_at: ".updated_at"
          platform: "'cursor'"
          connector: "'cursor'"

  list:
    operation: read
    label: "List messages"
    description: List messages in a conversation
    params:
      conversation_id: { type: string, required: true }
      limit: { type: number, default: 100 }
    sql:
      # Messages are stored separately as bubbleId:{composerId}:{bubbleId}
      # We get headers from composerData, then join with bubble data
      query: |
        WITH headers AS (
          SELECT 
            json_extract(header.value, '$.bubbleId') as bubble_id,
            json_extract(header.value, '$.type') as msg_type,
            header.key as sort_order
          FROM cursorDiskKV as conv,
               json_each(json_extract(conv.value, '$.fullConversationHeadersOnly')) as header
          WHERE conv.key = 'composerData:{{params.conversation_id}}'
        )
        SELECT 
          json_extract(bubble.value, '$.bubbleId') as id,
          '{{params.conversation_id}}' as conversation_id,
          json_extract(bubble.value, '$.text') as content,
          'markdown' as content_type,
          CASE json_extract(bubble.value, '$.type')
            WHEN 1 THEN 'user'
            WHEN 2 THEN 'bot'
            ELSE 'system'
          END as sender_type,
          CASE json_extract(bubble.value, '$.type')
            WHEN 1 THEN 'User'
            WHEN 2 THEN 'Assistant'
            ELSE 'System'
          END as sender_name,
          json_extract(bubble.value, '$.type') = 1 as is_outgoing,
          json_extract(bubble.value, '$.createdAt') as timestamp
        FROM headers
        JOIN cursorDiskKV as bubble 
          ON bubble.key = 'bubbleId:{{params.conversation_id}}:' || headers.bubble_id
        ORDER BY headers.sort_order
        LIMIT {{params.limit | default: 100}}
      response:
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            type: "[].sender_type"
            name: "[].sender_name"
            is_self: "[].is_outgoing"
          is_outgoing: "[].is_outgoing"
          timestamp: "[].timestamp"
          connector: "'cursor'"

  get:
    operation: read
    label: "Get message"
    description: Get a specific message by ID
    params:
      message_id: { type: string, required: true }
      conversation_id: { type: string, required: true }
    sql:
      query: |
        SELECT 
          json_extract(value, '$.bubbleId') as id,
          '{{params.conversation_id}}' as conversation_id,
          json_extract(value, '$.text') as content,
          'markdown' as content_type,
          CASE json_extract(value, '$.type')
            WHEN 1 THEN 'user'
            WHEN 2 THEN 'bot'
            ELSE 'system'
          END as sender_type,
          CASE json_extract(value, '$.type')
            WHEN 1 THEN 'User'
            WHEN 2 THEN 'Assistant'
            ELSE 'System'
          END as sender_name,
          json_extract(value, '$.type') = 1 as is_outgoing,
          json_extract(value, '$.createdAt') as timestamp
        FROM cursorDiskKV
        WHERE key = 'bubbleId:{{params.conversation_id}}:{{params.message_id}}'
      response:
        mapping:
          id: ".id"
          conversation_id: ".conversation_id"
          content: ".content"
          content_type: ".content_type"
          sender:
            type: ".sender_type"
            name: ".sender_name"
            is_self: ".is_outgoing"
          is_outgoing: ".is_outgoing"
          timestamp: ".timestamp"
          connector: "'cursor'"

  search:
    operation: read
    label: "Search messages"
    description: Search messages across all conversations
    params:
      query: { type: string, required: true }
      limit: { type: number, default: 50 }
    sql:
      # Search all bubble messages for text content
      query: |
        SELECT 
          json_extract(bubble.value, '$.bubbleId') as id,
          substr(bubble.key, 10, instr(substr(bubble.key, 10), ':') - 1) as conversation_id,
          json_extract(bubble.value, '$.text') as content,
          'markdown' as content_type,
          CASE json_extract(bubble.value, '$.type')
            WHEN 1 THEN 'user'
            WHEN 2 THEN 'bot'
            ELSE 'system'
          END as sender_type,
          CASE json_extract(bubble.value, '$.type')
            WHEN 1 THEN 'User'
            WHEN 2 THEN 'Assistant'
            ELSE 'System'
          END as sender_name,
          json_extract(bubble.value, '$.type') = 1 as is_outgoing,
          json_extract(bubble.value, '$.createdAt') as timestamp
        FROM cursorDiskKV as bubble
        WHERE bubble.key LIKE 'bubbleId:%'
          AND json_extract(bubble.value, '$.text') LIKE '%{{params.query}}%'
        ORDER BY json_extract(bubble.value, '$.createdAt') DESC
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          conversation_id: "[].conversation_id"
          content: "[].content"
          content_type: "[].content_type"
          sender:
            type: "[].sender_type"
            name: "[].sender_name"
            is_self: "[].is_outgoing"
          is_outgoing: "[].is_outgoing"
          timestamp: "[].timestamp"
          connector: "'cursor'"
---

# Cursor

AI code editor conversation history integration.

## Overview

Cursor stores chat/composer history in a local SQLite database. This connector provides read-only access to past AI conversations.

## Data Structure

The database uses a key-value store (`cursorDiskKV` table) with two key patterns:

### 1. Conversations: `composerData:{uuid}`

```json
{
  "composerId": "uuid",
  "name": "Conversation title",
  "createdAt": "2025-12-23T21:46:41.398Z",
  "lastUpdatedAt": 1703123789000,
  "fullConversationHeadersOnly": [
    { "bubbleId": "uuid-1", "type": 1 },
    { "bubbleId": "uuid-2", "type": 2 }
  ],
  "unifiedMode": "agent",
  "context": { ... }
}
```

### 2. Messages: `bubbleId:{composerId}:{bubbleId}`

```json
{
  "bubbleId": "uuid",
  "type": 1,  // 1=user, 2=assistant
  "text": "How do I fix this bug?",
  "richText": { ... },
  "createdAt": "2025-12-23T21:46:41.398Z",
  "isAgentic": true,
  "toolResults": [ ... ],
  "codeBlocks": [ ... ]
}
```

**Note:** Message content is stored separately from conversation metadata. The `fullConversationHeadersOnly` array contains bubble IDs and types, while actual content is in separate `bubbleId:` keys.

## Features

- List all AI chat conversations
- Get messages from a specific conversation
- Search across all conversations
- Read-only access (no write operations)
