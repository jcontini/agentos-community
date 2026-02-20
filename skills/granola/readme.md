---
id: granola
name: Granola
description: Meeting transcripts and AI summaries from Granola
icon: icon.svg
color: "#2D6A4F"

website: https://granola.ai
privacy_url: https://granola.ai/privacy

auth: none
platforms: [macos]
connects_to: granola

seed:
  - id: granola
    types: [software]
    name: Granola
    data:
      software_type: app
      url: https://granola.ai
      platforms: [macos, windows]
      pricing: freemium
    relationships:
      - role: offered_by
        to: granola-inc

  - id: granola-inc
    types: [organization]
    name: Granola, Inc.
    data:
      type: company
      url: https://granola.ai

instructions: |
  Granola meeting transcripts and AI summaries.

  - Auth is automatic — reads local token from ~/Library/Application Support/Granola/supabase.json
  - Token expires every ~6 hours; open Granola to auto-refresh if you get auth errors
  - meeting.list returns recent meetings with attendee metadata (no transcript, fast)
  - meeting.get returns a full meeting: transcript as a linked transcript entity, AI summary, attendees
  - meeting.search uses Granola's semantic search across all meetings
  - Transcripts are FTS5-indexed for full-text search after meeting.get is called

requires:
  - name: Granola
    install:
      macos: Download from https://granola.ai

transformers:
  meeting:
    terminology: Meeting
    mapping:
      id: .id
      title: .title
      start: .start
      end: .end
      description: .summary_text
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
          _body: .transcript_text
          _body_role: '"transcript"'
          language: '"en"'
          source_type: '"realtime_asr"'
          segment_count: .segment_count
          duration_ms: .duration_ms

operations:
  meeting.list:
    description: List recent meetings with metadata and attendees
    returns: meeting[]
    params:
      limit: { type: integer, default: 20, description: "Number of meetings to return" }
      page: { type: integer, default: 0, description: "Page number (0-indexed)" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/granola/granola.py list {{params.limit}} {{params.page}}"
      timeout: 30

  meeting.get:
    description: Get a meeting with full transcript, attendees, and AI summary
    returns: meeting
    params:
      id: { type: string, required: true, description: "Granola document ID (UUID)" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/granola/granola.py get {{params.id}}"
      timeout: 60

  meeting.search:
    description: Semantic search across meetings using Granola's embeddings
    returns: meeting[]
    params:
      query: { type: string, required: true, description: "Search query" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ~/dev/agentos-community/skills/granola/granola.py search {{params.query}}"
      timeout: 30

---

# Granola

Meeting transcripts and AI summaries from [Granola](https://granola.ai) — automatically captured as you meet.

## Setup

Granola must be installed and have run at least once. No API key needed — auth is read directly from Granola's local token file.

If you see auth errors, open the Granola app to refresh the token.

## What gets created in the graph

For each `meeting.get` call:

| Entity | Type | Details |
|--------|------|---------|
| The meeting | `meeting` | Title, times, location, AI summary as description |
| Transcript | `transcript` | Full text body (FTS5-indexed), segment count, duration |

Relationships:
- `transcript --transcribe--> meeting`

Attendees are stored in `data.attendees` on the meeting entity. Full person entity creation from attendees is a future enhancement.

## Operations

### `meeting.list` — Browse recent meetings

```bash
curl -X POST http://localhost:3456/api/skills/granola/meeting.list \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

Returns meetings with title, times, location, attendees. No transcript data — use `meeting.get` for that.

### `meeting.get` — Full meeting with transcript

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

### `meeting.search` — Semantic search

```bash
curl -X POST http://localhost:3456/api/skills/granola/meeting.search \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{"query": "Docker security vulnerability"}'
```

Uses Granola's server-side embedding search. Complementary to local FTS5 search once transcripts are ingested.

## Transcript format

Transcripts are stored as plain text in the `transcript` entity body:

```
[00:02:34] You: What's the status on the deployment?
[00:02:41] Other: We hit a snag with the Docker config, but it's fixed now.
[00:02:58] You: Great. What's the timeline?
```

Speaker labels: `You` (microphone) and `Other` (system audio).
