---
id: opencode
name: OpenCode
description: CLI coding agent for Claude — conversation history, sub-agent research, and session data
icon: icon.svg
color: "#F97316"
platforms: [macos, linux]

website: https://opencode.ai

auth: none

database: "~/.local/share/opencode/opencode.db"

instructions: >
  You are running in OpenCode. Your conversation history and sub-agent research
  are stored locally in a SQLite database. Use this skill to search past sessions,
  find previous research, and recover sub-agent output that would otherwise be lost.

connects_to: opencode-app

seed:
  - id: opencode-app
    types: [software]
    name: OpenCode
    data:
      software_type: ai_client
      url: https://opencode.ai
      platforms: [macos, linux, windows]
    relationships: []

transformers:
  session:
    mapping:
      id: .id
      name: .title
      data.slug: .slug
      data.directory: .directory
      data.parent_id: .parent_id
      data.project_worktree: .project_worktree
      data.message_count: .message_count
      data.text_part_count: .text_part_count
      data.is_subagent: .is_subagent
      data.additions: .additions
      data.deletions: .deletions
      data.files_changed: .files_changed

operations:
  session.list:
    description: List OpenCode sessions, most recent first. Includes message counts and whether each session is a sub-agent.
    returns: session[]
    params:
      limit:
        type: integer
        description: Max sessions to return
      project:
        type: string
        description: Filter by project worktree path (e.g. /Users/joe/dev/agentos)
      subagents:
        type: boolean
        description: If true, only show sub-agent sessions (have a parent). If false, only top-level sessions.
    sql:
      query: |
        SELECT
          s.id,
          s.title,
          s.slug,
          s.directory,
          s.parent_id,
          p.worktree as project_worktree,
          CASE WHEN s.parent_id IS NOT NULL THEN 1 ELSE 0 END as is_subagent,
          s.summary_additions as additions,
          s.summary_deletions as deletions,
          s.summary_files as files_changed,
          (SELECT count(*) FROM message m WHERE m.session_id = s.id) as message_count,
          (SELECT count(*) FROM part pt WHERE pt.session_id = s.id AND json_extract(pt.data, '$.type') = 'text') as text_part_count,
          datetime(s.time_created / 1000, 'unixepoch') as created_at,
          datetime(s.time_updated / 1000, 'unixepoch') as updated_at
        FROM session s
        JOIN project p ON s.project_id = p.id
        WHERE (:project IS NULL OR p.worktree = :project)
          AND (:subagents IS NULL
               OR (:subagents = 1 AND s.parent_id IS NOT NULL)
               OR (:subagents = 0 AND s.parent_id IS NULL))
          AND s.time_archived IS NULL
        ORDER BY s.time_created DESC
        LIMIT :limit
      params:
        limit: ".params.limit // 50"
        project: ".params.project // null"
        subagents: ".params.subagents // null"

  session.get:
    description: Get a session with its full conversation transcript — all text parts in order.
    returns: session
    params:
      id:
        type: string
        required: true
        description: Session ID (e.g. ses_36ddbc1c9ffe...)
    sql:
      query: |
        SELECT
          s.id,
          s.title,
          s.slug,
          s.directory,
          s.parent_id,
          p.worktree as project_worktree,
          CASE WHEN s.parent_id IS NOT NULL THEN 1 ELSE 0 END as is_subagent,
          s.summary_additions as additions,
          s.summary_deletions as deletions,
          s.summary_files as files_changed,
          (SELECT count(*) FROM message m WHERE m.session_id = s.id) as message_count,
          datetime(s.time_created / 1000, 'unixepoch') as created_at,
          datetime(s.time_updated / 1000, 'unixepoch') as updated_at
        FROM session s
        JOIN project p ON s.project_id = p.id
        WHERE s.id = :id
      params:
        id: ".params.id"

  session.search:
    description: Search session titles for a keyword. Useful for finding past conversations by topic.
    returns: session[]
    params:
      query:
        type: string
        required: true
        description: Search term to match against session titles
      limit:
        type: integer
        description: Max results
    sql:
      query: |
        SELECT
          s.id,
          s.title,
          s.slug,
          s.directory,
          s.parent_id,
          p.worktree as project_worktree,
          CASE WHEN s.parent_id IS NOT NULL THEN 1 ELSE 0 END as is_subagent,
          (SELECT count(*) FROM message m WHERE m.session_id = s.id) as message_count,
          datetime(s.time_created / 1000, 'unixepoch') as created_at
        FROM session s
        JOIN project p ON s.project_id = p.id
        WHERE s.title LIKE '%' || :query || '%'
          AND s.time_archived IS NULL
        ORDER BY s.time_created DESC
        LIMIT :limit
      params:
        query: ".params.query"
        limit: ".params.limit // 20"

utilities:
  research:
    description: >
      Find sub-agent research output — the long text content produced by Task tool
      sub-agents during web research, code exploration, etc. Searches across all
      sub-agent sessions for text parts longer than a threshold. Returns the session
      title, text content, and metadata.
    returns: record[]
    params:
      query:
        type: string
        description: Search term to match in session titles or text content
      min_length:
        type: integer
        description: Minimum text length to qualify as research (default 2000)
      limit:
        type: integer
        description: Max results
      session_id:
        type: string
        description: Get research from a specific session only
    sql:
      query: |
        SELECT
          s.id as session_id,
          s.title as session_title,
          s.parent_id,
          p.worktree as project,
          json_extract(pt.data, '$.text') as content,
          length(json_extract(pt.data, '$.text')) as content_length,
          datetime(pt.time_created / 1000, 'unixepoch') as created_at
        FROM part pt
        JOIN message m ON pt.message_id = m.id
        JOIN session s ON m.session_id = s.id
        JOIN project p ON s.project_id = p.id
        WHERE json_extract(pt.data, '$.type') = 'text'
          AND length(json_extract(pt.data, '$.text')) >= :min_length
          AND s.parent_id IS NOT NULL
          AND (:query IS NULL
               OR s.title LIKE '%' || :query || '%'
               OR json_extract(pt.data, '$.text') LIKE '%' || :query || '%')
          AND (:session_id IS NULL OR s.id = :session_id)
        ORDER BY length(json_extract(pt.data, '$.text')) DESC
        LIMIT :limit
      params:
        query: ".params.query // null"
        min_length: ".params.min_length // 2000"
        limit: ".params.limit // 10"
        session_id: ".params.session_id // null"

  transcript:
    description: >
      Get the full text transcript of a session — all text parts concatenated in
      chronological order. Useful for reading what happened in a past conversation
      or sub-agent research session.
    returns: record[]
    params:
      session_id:
        type: string
        required: true
        description: Session ID to get transcript for
    sql:
      query: |
        SELECT
          json_extract(pt.data, '$.text') as text,
          json_extract(m.data, '$.role') as role,
          datetime(pt.time_created / 1000, 'unixepoch') as time
        FROM part pt
        JOIN message m ON pt.message_id = m.id
        WHERE pt.session_id = :session_id
          AND json_extract(pt.data, '$.type') = 'text'
        ORDER BY pt.time_created ASC
      params:
        session_id: ".params.session_id"

  children:
    description: >
      List all sub-agent sessions spawned from a parent session.
      Shows what Task tool calls were made and their titles.
    returns: record[]
    params:
      parent_id:
        type: string
        required: true
        description: Parent session ID
    sql:
      query: |
        SELECT
          s.id,
          s.title,
          (SELECT count(*) FROM part pt
           WHERE pt.session_id = s.id
             AND json_extract(pt.data, '$.type') = 'text') as text_part_count,
          (SELECT max(length(json_extract(pt.data, '$.text')))
           FROM part pt
           WHERE pt.session_id = s.id
             AND json_extract(pt.data, '$.type') = 'text') as longest_text,
          datetime(s.time_created / 1000, 'unixepoch') as created_at
        FROM session s
        WHERE s.parent_id = :parent_id
        ORDER BY s.time_created ASC
      params:
        parent_id: ".params.parent_id"

testing:
  exempt:
    operations: Local database skill — requires OpenCode installation
---

# OpenCode

CLI coding agent for Claude. Conversation history, sub-agent research, and session data are stored locally in a SQLite database at `~/.local/share/opencode/opencode.db`.

## Finding Previous Research

When you or a previous agent used the Task tool to launch sub-agents for web research, code exploration, or deep analysis, that research is stored permanently in OpenCode's database. Use this skill to find and recover it.

```
# Search for research by topic
use({ skill: "opencode", tool: "research", params: { query: "Coda formula language" } })

# List recent sessions
use({ skill: "opencode", tool: "session.list", params: { limit: 10 } })

# List only sub-agent sessions
use({ skill: "opencode", tool: "session.list", params: { subagents: true, limit: 20 } })

# Search sessions by title
use({ skill: "opencode", tool: "session.search", params: { query: "Bahasa" } })

# Get full transcript of a specific session
use({ skill: "opencode", tool: "transcript", params: { session_id: "ses_..." } })

# See what sub-agents a session spawned
use({ skill: "opencode", tool: "children", params: { parent_id: "ses_..." } })

# Filter sessions by project
use({ skill: "opencode", tool: "session.list", params: { project: "/Users/joe/dev/agentos" } })
```

## Data Model

| Table | What it holds |
|-------|-------------|
| `session` | Conversations — each has a title, project, optional parent (sub-agents) |
| `message` | Messages within sessions — role (user/assistant), model, token counts |
| `part` | Parts of messages — text content, tool calls, tool results |
| `project` | Workspace/project definitions — maps project IDs to directory paths |

Sub-agent sessions have a `parent_id` pointing to the session that spawned them. The `research` utility finds the longest text outputs from sub-agent sessions — these are typically the synthesis/summary reports that contain the most valuable research.

## Database Location

| Platform | Path |
|----------|------|
| macOS | `~/.local/share/opencode/opencode.db` |
| Linux | `~/.local/share/opencode/opencode.db` |

Other OpenCode data:
- Config: `~/.config/opencode/opencode.json`
- Logs: `~/.local/share/opencode/log/`
- Tool output overflow: `~/.local/share/opencode/tool-output/`
- Prompt history: `~/.local/state/opencode/prompt-history.jsonl`
