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
  find previous research, recover sub-agent output, and call other workspace agents.
  Use agent.ask to call another project's agent when you need domain knowledge —
  the agent wakes up in its workspace with full context and answers your question.

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

      content: .transcript_text

  document:
    mapping:
      id: .id
      name: .title
      content: .content
      data.source_session_id: .session_id
      data.source_session_title: .session_title
      data.content_length: .content_length
      data.project: .project

operations:
  session.list:
    description: List OpenCode sessions, most recent first. Includes message counts and whether each session is a sub-agent. Use parent_id to list sub-agent sessions spawned from a specific session.
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
      parent_id:
        type: string
        description: List sub-agent sessions spawned from this parent session ID
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
          AND (:parent_id IS NULL OR s.parent_id = :parent_id)
          AND s.time_archived IS NULL
        ORDER BY s.time_created DESC
        LIMIT :limit
      params:
        limit: ".params.limit // 50"
        project: ".params.project // null"
        subagents: ".params.subagents // null"
        parent_id: ".params.parent_id // null"

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

  session.import:
    description: >
      Import OpenCode sessions with their full conversation transcripts into the Memex.
      Each session becomes a session entity, and its transcript becomes a transcript entity
      linked via a transcribe relationship. Content is FTS5-indexed for full-text search.
      Use since to import only recent sessions. Deduplicates via service_id — safe to run repeatedly.
    returns: session[]
    params:
      since:
        type: integer
        description: Only import sessions from the last N days (default all)
      project:
        type: string
        description: Filter by project worktree path
      limit:
        type: integer
        description: Max sessions to import (default 100)
      subagents:
        type: boolean
        description: If true, only import sub-agent sessions. If false, only top-level.
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
          (SELECT group_concat(
            CASE json_extract(m2.data, '$.role')
              WHEN 'user' THEN '## User' || char(10) || json_extract(pt2.data, '$.text')
              WHEN 'assistant' THEN '## Assistant' || char(10) || json_extract(pt2.data, '$.text')
              ELSE json_extract(pt2.data, '$.text')
            END,
            char(10) || char(10)
          ) FROM part pt2
           JOIN message m2 ON pt2.message_id = m2.id
           WHERE pt2.session_id = s.id
             AND json_extract(pt2.data, '$.type') = 'text'
           ORDER BY pt2.time_created ASC
          ) as transcript_text,
          datetime(s.time_created / 1000, 'unixepoch') as created_at,
          datetime(s.time_updated / 1000, 'unixepoch') as updated_at
        FROM session s
        JOIN project p ON s.project_id = p.id
        WHERE s.time_archived IS NULL
          AND (:project IS NULL OR p.worktree = :project)
          AND (:subagents IS NULL
               OR (:subagents = 1 AND s.parent_id IS NOT NULL)
               OR (:subagents = 0 AND s.parent_id IS NULL))
          AND (:since IS NULL
               OR s.time_created >= (strftime('%s', 'now') - :since * 86400) * 1000)
        ORDER BY s.time_created DESC
        LIMIT :limit
      params:
        limit: ".params.limit // 100"
        project: ".params.project // null"
        subagents: ".params.subagents // null"
        since: ".params.since // null"

  research.import:
    description: >
      Import sub-agent research output as document entities on the Memex. Finds long text
      content produced by Task tool sub-agents and creates searchable document entities.
      Each research output gets its own entity with full FTS5 indexing.
    returns: document[]
    params:
      query:
        type: string
        description: Search term to filter by session title or content
      min_length:
        type: integer
        description: Minimum text length to qualify as research (default 2000)
      limit:
        type: integer
        description: Max results to import
      since:
        type: integer
        description: Only import research from the last N days
    sql:
      query: |
        SELECT
          s.id || '_research_' || pt.id as id,
          'Research: ' || s.title as title,
          json_extract(pt.data, '$.text') as content,
          s.id as session_id,
          s.title as session_title,
          length(json_extract(pt.data, '$.text')) as content_length,
          p.worktree as project,
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
          AND (:since IS NULL
               OR pt.time_created >= (strftime('%s', 'now') - :since * 86400) * 1000)
        ORDER BY pt.time_created DESC
        LIMIT :limit
      params:
        query: ".params.query // null"
        min_length: ".params.min_length // 2000"
        limit: ".params.limit // 50"
        since: ".params.since // null"

utilities:
  ask:
    description: |
      Call another workspace agent via OpenCode's non-interactive mode.
      Resolves a project name to a workspace path via the Memex, then
      invokes `opencode run --dir <path>` with the question. The called
      agent wakes up in its workspace with full context (AGENTS.md, MCP
      servers, readme) and answers the question. Returns the text response.
      The call creates a session in the target workspace's OpenCode history.

      Use this when you need domain knowledge from another project —
      like calling a colleague who works on that codebase.
    params:
      project:
        type: string
        required: true
        description: Project name to call (e.g. "agentOS", "Pathway Agents")
      question:
        type: string
        required: true
        description: The question to ask the agent
      model:
        type: string
        description: "Model override (e.g. anthropic/claude-sonnet-4-20250514). Defaults to caller's model."
    returns:
      answer: string
      project_name: string
      project_id: string
      workspace_path: string
    command:
      binary: bash
      args:
        - "-c"
        - "bash ~/dev/agentos-community/skills/opencode/agent-ask.sh '{{params.project}}' '{{params.question}}' '{{params.model}}'"
      timeout: 120

testing:
  exempt:
    operations: Local database skill — requires OpenCode installation
---

# OpenCode

CLI coding agent for Claude. Conversation history, sub-agent research, and session data are stored locally in a SQLite database at `~/.local/share/opencode/opencode.db`.

## Importing Data into the Memex

OpenCode sessions and research can be imported into the Memex as proper entities, making them searchable via FTS5. Once imported, "what did we talk about last week?" just works.

```
# Import last 7 days of sessions with transcripts
use({ skill: "opencode", tool: "session.import", params: { since: 7 } })

# Import all sessions for a specific project
use({ skill: "opencode", tool: "session.import", params: { project: "/Users/joe/dev/agentOS" } })

# Import sub-agent research as searchable documents
use({ skill: "opencode", tool: "research.import", params: { since: 7 } })

# Import research matching a topic
use({ skill: "opencode", tool: "research.import", params: { query: "Coda formula language" } })
```

Import is safe to run repeatedly — deduplicates via service_id. Each session becomes a session entity with the full conversation transcript as its body content, directly FTS5-indexed. Research outputs become document entities.

## Browsing Sessions

```
# List recent sessions
use({ skill: "opencode", tool: "session.list", params: { limit: 10 } })

# List only sub-agent sessions
use({ skill: "opencode", tool: "session.list", params: { subagents: true, limit: 20 } })

# List sub-agents spawned from a specific session
use({ skill: "opencode", tool: "session.list", params: { parent_id: "ses_..." } })

# Search sessions by title
use({ skill: "opencode", tool: "session.search", params: { query: "Bahasa" } })

# Get a specific session with transcript
use({ skill: "opencode", tool: "session.get", params: { id: "ses_..." } })

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

Sub-agent sessions have a `parent_id` pointing to the session that spawned them. Research import finds the longest text outputs from sub-agent sessions — these are typically the synthesis/summary reports that contain the most valuable research.

## Calling Other Agents

OpenCode can invoke agents in other workspaces non-interactively. Each project in the Memex is linked to a workspace folder — the skill resolves the project name, finds the path, and runs `opencode run --dir <path>` with your question.

```
# Ask the agentOS agent a question
use({ skill: "opencode", tool: "ask", params: {
  project: "agentOS",
  question: "How do I add tasks to a project roadmap?"
}})

# Ask with a specific model
use({ skill: "opencode", tool: "ask", params: {
  project: "Pathway Agents",
  question: "What countries does the pipeline support?",
  model: "anthropic/claude-sonnet-4-20250514"
}})
```

The called agent wakes up in its workspace with full context — AGENTS.md, MCP servers, readme — answers the question, and returns. Like calling a colleague at their desk.

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
