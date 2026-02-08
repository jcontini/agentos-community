---
id: cursor
name: Cursor
description: Search and access Cursor AI conversation history
icon: icon.svg

website: https://cursor.com


adapters:
  conversation:
    mapping:
      id: .id
      title: .title
      project: .project
      created_at: .created_at
      message_count: .message_count

  message:
    mapping:
      id: .id
      role: .role
      content: .content
      timestamp: .timestamp
      conversation_id: .conversation_id

operations:
  conversation.list:
    description: List all Cursor conversations across projects
    readonly: true
    params:
      project: { type: string, description: "Filter by project name" }
      limit: { type: integer, default: 50 }
    returns: conversation[]
    command:
      binary: node
      args: ["scripts/cursor.mjs", "list", "{{params | json}}"]

  conversation.get:
    description: Get a conversation with all messages
    readonly: true
    params:
      id: { type: string, required: true }
    returns: conversation
    command:
      binary: node
      args: ["scripts/cursor.mjs", "get", "{{params | json}}"]

  conversation.search:
    description: Search conversations by content
    readonly: true
    params:
      query: { type: string, required: true }
      project: { type: string }
      limit: { type: integer, default: 20 }
    returns: conversation[]
    command:
      binary: node
      args: ["scripts/cursor.mjs", "search", "{{params | json}}"]
---

# Cursor

Search and access your Cursor AI conversation history. Enables cross-session search and context recovery.

## Data Sources

| Source | Location | Format |
|--------|----------|--------|
| Transcripts | `~/.cursor/projects/{project}/agent-transcripts/*.txt` | Plain text (most complete) |
| State DB | `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb` | SQLite KV |

## Key Insight

The `agent-transcripts/` folder contains plain text conversation history:
- Role labels: `user:`, `assistant:`, `[Tool call]`, `[Tool result]`
- One file per conversation (UUID filename)
- Updated in real-time during sessions

**Gotcha:** Project folder name varies based on how Cursor was opened:
- Directory `/Users/joe/dev/agentos/` → `Users-joe-dev-agentos/`
- Workspace file → `Users-joe-dev-agentos-AgentOS-code-workspace/`

## Use Cases

- "Find where we discussed the firewall design"
- "What was the exact error message from yesterday's debugging?"
- "Show me all conversations about the entity graph"
- Recovering context after session summarization loses details

## Implementation Notes

- Read-only (no write operations)
- Scans all `~/.cursor/projects/*/agent-transcripts/` folders
- Parses plain text format (regex on role markers)
- Indexes by timestamp, project, content
