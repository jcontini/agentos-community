---
id: cursor
name: Cursor
description: AI-powered code editor conversation history
icon: icon.png
color: "#00D1FF"

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
