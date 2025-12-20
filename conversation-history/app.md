---
id: conversation-history
name: Conversation History
description: Query your local Cursor conversation history - list recent chats, search by keyword, see files modified
icon: material-symbols:history
color: "#8B5CF6"

tags: [conversation history, Cursor chats, Claude chats, ChatGPT history]

requires:
  - python3

settings:
  default_agent:
    label: Default Agent
    description: Which agent to query by default
    type: enum
    default: "cursor"
    options:
      - cursor
      - all
  default_limit:
    label: Default Results
    description: Number of results to show by default
    type: integer
    default: "30"
    min: 5
    max: 100

helpers: |
  history() {
    python3 "$PLUGIN_DIR/scripts/history.py" "$@"
  }

actions:
  list:
    readonly: true
    description: List recent conversations from AI agents with date, workspace, name, and file types modified
    params:
      agent:
        type: string
        default: "cursor"
        description: "Agent to query: cursor, claude, or all"
      limit:
        type: integer
        default: "30"
        description: Maximum number of conversations to return
      format:
        type: string
        default: "table"
        description: "Output format: table or json"
    run: |
      history list \
        --agent "${PARAM_AGENT:-${SETTING_DEFAULT_AGENT:-cursor}}" \
        --limit "${PARAM_LIMIT:-${SETTING_DEFAULT_LIMIT:-30}}" \
        --format "${PARAM_FORMAT:-table}"

  search:
    readonly: true
    description: Search conversations by keyword across name, workspace, and files modified
    params:
      query:
        type: string
        required: true
        description: Search term to find in conversation names, workspaces, or file names
      agent:
        type: string
        default: "cursor"
        description: "Agent to query: cursor, claude, or all"
      limit:
        type: integer
        default: "30"
        description: Maximum number of results to return
      format:
        type: string
        default: "table"
        description: "Output format: table or json"
    run: |
      history search \
        --agent "${PARAM_AGENT:-${SETTING_DEFAULT_AGENT:-cursor}}" \
        --query "$PARAM_QUERY" \
        --limit "${PARAM_LIMIT:-${SETTING_DEFAULT_LIMIT:-30}}" \
        --format "${PARAM_FORMAT:-table}"

  agents:
    readonly: true
    description: List available agents and their status (installed, paths found)
    run: |
      history agents
---

# Conversation History

Find and search your AI conversation history across different agents.

## ⚠️ IMPORTANT: Output Formatting

**The tool output is already formatted as markdown tables. Display it EXACTLY as returned.**

DO NOT reformat the output into bullet points or plain text. The tool returns:
- `## Date Headers` (Today, Yesterday, weekday names)
- Markdown tables with `| Time | Name | Files |` columns

**Correct presentation:**

## Today

| Time | Name | Files |
|------|------|-------|
| 09:02 | Cursor conversation history location | .py, .md (2) |
| 08:59 | AGE52 refactor dependencies in Linear | .md (1) |

## Yesterday

| Time | Name | Files |
|------|------|-------|
| 16:37 | BLU token investment and taxes | .md (4) |
| 14:49 | 2025 personal financial statement | .md, .csv (3) |

**Wrong presentation:**
```
Today:
09:02 - Cursor conversation history location (.py, .md files)
```

Copy the tool output verbatim — it's already properly formatted markdown.

---

## Quick Start

List recent conversations:
```
tool: list
```

Search for a specific topic:
```
tool: search
params: {query: "investments"}
```

## Supported Agents

| Agent | Status | Platform |
|-------|--------|----------|
| **Cursor** | ✅ Supported | macOS (Linux/Windows paths ready) |
| **Claude Desktop** | 🚧 Planned | - |

## Tools

### list ⚡ (start here)
List recent conversations grouped by date with time, name, and files.

```
tool: list
```

With more results:
```
tool: list
params: {limit: 50}
```

As JSON (for programmatic use):
```
tool: list
params: {format: "json"}
```

### search
Find conversations by keyword in name, workspace, or files.

```
tool: search
params: {query: "typescript"}
```

Search for workspace:
```
tool: search
params: {query: "agentos"}
```

Search across all agents:
```
tool: search
params: {query: "finance", agent: "all"}
```

### agents
Check which agents are available and their storage paths.

```
tool: agents
```

## JSON Output

Use `format: "json"` for structured data with additional fields:

- `workspace` / `workspace_path` - Project folder
- `modified_date` / `modified_time` - Timestamps
- `lines_added` / `lines_removed` - Code changes
- `files_changed` - Number of files modified
- `file_types` - Breakdown by extension `{"rs": 3, "md": 2}`
- `subtitle` - Specific files being worked on
- `archived` - If conversation is archived

## Tips

1. **Start with `list`** to see recent activity
2. **Use `search`** when you remember a keyword from the conversation
3. **Use JSON format** when you need to process results programmatically
4. **Search by file type** - e.g., "svelte" finds Svelte conversations

## Architecture

This plugin is designed to be extensible:

- **Multi-agent**: Each agent (Cursor, Claude) has its own handler
- **Multi-platform**: Paths configured for macOS, Linux, Windows
- **Consistent API**: All agents return the same data structure
