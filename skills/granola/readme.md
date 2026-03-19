---
id: granola
name: Granola
description: Meeting transcripts, AI summaries, and Q&A conversations from Granola
icon: icon.svg
color: "#2D6A4F"

website: https://granola.ai
privacy_url: https://granola.ai/privacy

connections: {}

# Auth is handled internally by granola.py — reads WorkOS token from
# ~/Library/Application Support/Granola/supabase.json.
# Cache reads ~/Library/Application Support/Granola/cache-v6.json.
# No runtime credential injection needed; Python self-authenticates.

adapters:
  meeting:
    id: .id
    name: .title
    description: .summary_text
    text: .summary_text
    url: .granola_url
    datePublished: .start
    title: .title
    start: .start
    end: .end
    location: .location
    data.calendar_link: .calendar_link
    data.granola_url: .granola_url
    data.creation_source: .creation_source
    data.valid_meeting: .valid_meeting
    data.organizer_email: .organizer_email
    data.organizer_name: .organizer_name
    data.attendees: .attendees

    transcribe:
      transcript:
        id: '(.id) + "_transcript"'
        title: '"Transcript: " + .title'
        content: .transcript_text
        content_role: '"transcript"'
        language: '"en"'
        source_type: '"realtime_asr"'
        segment_count: .segment_count
        duration_ms: .duration_ms

  conversation:
    id: .id
    name: .title
    text: 'if .messages then (.messages | map(.text) | join("\n\n")) else "" end'
    content: 'if .messages then (.messages | map(.text) | join("\n\n")) else "" end'
    url: .notes_url
    # Last activity (same idea as imessage/claude conversation adapters)
    datePublished: .updated_at
    data.created_at: .created_at
    data.updated_at: .updated_at
    data.document_id: .document_id
    data.message_count: 'if .messages then (.messages | length) else null end'

operations:
  list_meetings:
    description: List recent meetings with metadata and attendees
    returns: meeting[]
    params:
      limit: { type: integer, description: "Number of meetings to return" }
      page: { type: integer, default: 0, description: "Page number (0-indexed)" }
      source: { type: string, default: "api", description: "api | cache | auto — cache works offline" }
    python:
      module: ./granola.py
      function: op_list_meetings
      args:
        limit: '.params.limit // 20'
        page: '.params.page // 0'
        source: '.params.source // "api"'
      timeout: 30

  get_meeting:
    description: Get a meeting with full transcript, attendees, and AI summary
    returns: meeting
    params:
      id: { type: string, required: true, description: "Granola document ID (UUID)" }
    python:
      module: ./granola.py
      function: op_get_meeting
      args:
        id: .params.id
      timeout: 60

  list_conversations:
    description: List Q&A/AI chat threads linked to a meeting transcript
    returns: conversation[]
    params:
      document_id: { type: string, required: true, description: "Meeting document ID (UUID)" }
      source: { type: string, default: "api", description: "api | cache | auto — cache works offline" }
    python:
      module: ./granola.py
      function: op_list_conversations
      args:
        document_id: .params.document_id
        source: '.params.source // "api"'
      timeout: 30

  get_conversation:
    description: Get a Q&A conversation with full message history
    returns: conversation
    params:
      thread_id: { type: string, required: true, description: "Chat thread ID (UUID)" }
      source: { type: string, default: "api", description: "api | cache | auto — cache works offline" }
    python:
      module: ./granola.py
      function: op_get_conversation
      args:
        thread_id: .params.thread_id
        source: '.params.source // "api"'
      timeout: 30

---

# Granola

Meeting transcripts and AI summaries from [Granola](https://granola.ai) — automatically captured as you meet.

## Setup

Granola must be installed and have run at least once. No API key needed — auth is read directly from Granola's local token file.

If you see auth errors, open the Granola app to refresh the token.

## API + Cache

This skill supports two data sources:

| Source | When | Use case |
|--------|------|----------|
| **api** | Live calls with token | Freshest data, full transcripts |
| **cache** | Reads local cache-v6.json | Instant, works offline, token expired |
| **auto** | Try API, fall back to cache | Resilient — best of both |

Pass `source: "cache"` or `source: "auto"` on `list_meetings`, `list_conversations`, and `get_conversation` to use the cache. `get_meeting` is API-only (cache has no transcript text).

## What gets created in the graph

For each `get_meeting` call:

| Entity | Type | Details |
|--------|------|---------|
| The meeting | `meeting` | Title, times, location, AI summary as description |
| Transcript | `transcript` | Full text body (FTS5-indexed), segment count, duration |

Relationships:
- `transcript --transcribe--> meeting`

Attendees are stored in `data.attendees` on the meeting entity. Full person entity creation from attendees is a future enhancement.

## Operations

### `list_meetings` — Browse recent meetings

```bash
curl -X POST http://localhost:3456/api/skills/granola/meeting.list \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

Returns meetings with title, times, location, attendees. No transcript data — use `get_meeting` for that.

### `get_meeting` — Full meeting with transcript

```bash
curl -X POST http://localhost:3456/api/skills/granola/meeting.get \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"id": "2fbc5ac2-..."}'
```

Returns the full meeting including:
- Transcript as a linked `transcript` entity (FTS5-indexed)
- AI summary as the meeting `description`
- All attendees with enrichment (name, avatar, job title)

## Transcript format

Transcripts are stored as plain text in the `transcript` entity body:

```
[00:02:34] You: What's the status on the deployment?
[00:02:41] Other: We hit a snag with the Docker config, but it's fixed now.
[00:02:58] You: Great. What's the timeline?
```

Speaker labels: `You` (microphone) and `Other` (system audio).

## Q&A conversations

Granola lets you chat with AI about meeting transcripts. Each meeting can have one or more Q&A threads.

### What this is in the Memex

Each thread is a **`conversation` entity** — the same ontological kind as chat threads from Claude, iMessage, Mimestream/Gmail, and WhatsApp. The graph cares *what* it is (a named thread with messages and a URL), not which app produced it. `list_conversations` returns thin rows (title, ids, `notes_url`); `get_conversation` fills `text` / `content` by joining message bodies. The `document_id` you pass is the **meeting** document id in Granola; treat it as “which meeting this Q&A is about” when reasoning, even though the remembered entity type for the thread itself is still `conversation`.

### Workflow: Find AI chats about a meeting

1. **Get the meeting id** — `list_meetings` (or use the id from a meeting summary)
2. **List threads** — `list_conversations(document_id: meeting_id)` → returns thread(s) with titles and ids
3. **Read a thread** — `get_conversation(thread_id: thread_id)` → full user/assistant message history

Via AgentOS MCP:

```
run({ skill: "granola", tool: "list_meetings", params: { limit: 10 } })
run({ skill: "granola", tool: "list_conversations", params: { document_id: "<id from step 1>" } })
run({ skill: "granola", tool: "get_conversation", params: { thread_id: "<id from step 2>" } })
```

### `list_conversations` — Q&A threads for a meeting

```bash
curl -X POST http://localhost:3456/api/skills/granola/conversation.list \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "6dc09094-1c7e-421d-86c1-2b23f924b34e"}'
```

Returns threads linked to that meeting (e.g. "Validator Agent and Auto Rewrite Loop"). Use `get_conversation` with a thread ID to read the full exchange.

### `get_conversation` — Full Q&A thread

```bash
curl -X POST http://localhost:3456/api/skills/granola/conversation.get \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "5c4516ae-1224-4e39-a642-a1b9b7e0e279"}'
```

Returns the thread with all user/assistant messages in order.
