---
id: granola
name: Granola
description: Meeting transcripts and AI summaries from Granola
icon: icon.svg
color: "#2D6A4F"

website: https://granola.ai
privacy_url: https://granola.ai/privacy

auth: none

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

operations:
  list_meetings:
    description: List recent meetings with metadata and attendees
    returns: meeting[]
    params:
      limit: { type: integer, description: "Number of meetings to return" }
      page: { type: integer, default: 0, description: "Page number (0-indexed)" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ./granola.py list ${PARAM_LIMIT} ${PARAM_PAGE}"
        - "--"
        - ".params.limit"
        - ".params.page"
      working_dir: .
      timeout: 30

  get_meeting:
    description: Get a meeting with full transcript, attendees, and AI summary
    returns: meeting
    params:
      id: { type: string, required: true, description: "Granola document ID (UUID)" }
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - "python3 ./granola.py get ${PARAM_ID}"
        - "--"
        - ".params.id"
      working_dir: .
      timeout: 60

---

# Granola

Meeting transcripts and AI summaries from [Granola](https://granola.ai) — automatically captured as you meet.

## Setup

Granola must be installed and have run at least once. No API key needed — auth is read directly from Granola's local token file.

If you see auth errors, open the Granola app to refresh the token.

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
