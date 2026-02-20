---
id: cursor
name: Cursor
description: AI-first code editor with built-in MCP support
icon: icon.png
color: "#3B82F6"
platforms: [macos, windows, linux]

website: https://cursor.com

auth: none

instructions: >
  You are running in Cursor. MCP config: ~/.cursor/mcp.json.
  To reload without restart: rename mcp.json → mcp.json.bak → back to mcp.json, then sleep 1s.
  Research archive: run extract-research.py in this skill's directory to save sub-agent research to .research/.

connects_to: cursor-app

seed:
  - id: cursor-app
    types: [software]
    name: Cursor
    data:
      software_type: ai_client
      url: https://cursor.com
      platforms: [macos, windows, linux]
    relationships: []

testing:
  exempt:
    operations: Guide-only skill — no API operations
---

# Cursor

AI-first code editor with built-in MCP support.

## Setup

1. Click **Install to Cursor** in agentOS
2. Restart Cursor to load the MCP configuration
3. Your apps will be available automatically

MCP config locations:
- macOS/Linux: `~/.cursor/mcp.json`
- Windows: `%APPDATA%/Cursor/mcp.json`

## Instructions for AI

You are running in Cursor.

- MCP config: `~/.cursor/mcp.json`
- To reload MCP config: rename `~/.cursor/mcp.json` → `mcp.json.bak` → then back to `mcp.json` (triggers hot reload without restart)
- If any apps are disconnected or inaccessible, reload the MCP config using the rename trick above, sleep exactly 1 second, then try again

## Recommended settings

When the user asks to configure Cursor or improve their setup, offer these settings. Settings file: macOS `~/Library/Application Support/Cursor/User/settings.json`, Linux `~/.config/Cursor/User/settings.json`, Windows `%APPDATA%\Cursor\User\settings.json`. Preserve existing settings; only add or update what's requested.

| Setting | Value | Why |
|---------|-------|-----|
| `workbench.editorAssociations` | `{ "*.md": "vscode.markdown.preview.editor" }` | Open markdown files in preview by default; double-click to edit |
| `review.showInEditor` | `true` | Show AI diffs inline in the editor instead of a separate review panel |
| `review.enableAutoOpen` | `false` | Don't auto-open the review panel when AI makes changes |
| `cursor.fileReview.forceLegacyMode` | `true` | Open files directly in the editor instead of the review UI |
| `cursor.experimental.reviewWorkflow.enabled` | `false` | Disable the forced review workflow; use Git for review instead |

Restart Cursor after changing settings for them to take effect.

---

## Research Archive System

When Cursor's AI agent uses the Task tool to launch sub-agents for web research, those sub-agents produce rich markdown research reports. These reports are stored in Cursor's internal database and can be extracted into `.research/` directories for permanent reference.

### Where Cursor stores sub-agent data

All conversation data lives in a single SQLite database:

```
~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
```

- **Table:** `cursorDiskKV` (key-value store)
- **Blob keys:** `agentKv:blob:{sha256_hash}` — each is a JSON message from a conversation
- **Sub-agent Task results:** blobs with `role: "tool"` and `content[0].toolName: "Task"`

Each Task result blob contains:
- `content[0].result` — the final sub-agent output text (summary)
- `content[0].toolCallId` — links to the workspace via `task-{toolCallId}` composers
- `providerOptions.cursor.highLevelToolCallResult.output.success`:
  - `conversationSteps[]` — the **full sub-agent conversation transcript** (every thinking step, web search, URL fetch, intermediate message)
  - `agentId` — the sub-agent's UUID
  - `durationMs` — total runtime

### How workspace mapping works

The chain from blob → workspace:

1. Each blob has a `toolCallId` in its JSON
2. Cursor creates a composer entry `task-{toolCallId}` in the workspace's state DB
3. Workspace state DBs: `~/Library/Application Support/Cursor/User/workspaceStorage/{hash}/state.vscdb`
4. Conversation list: `ItemTable` → key `composer.composerData` → `allComposers[]`
5. Workspace path: `workspaceStorage/{hash}/workspace.json` → `folder` field

### The .research/ directory

Research reports are saved as markdown files with YAML front matter in a project's `.research/` directory.

**Naming convention:** `YYYY-MM-DD-slug.md`

**Front matter schema:**

```yaml
---
date: 2026-02-12
topic: Human-readable title
source:
  type: cursor-subagent
  blob_key: agentKv:blob:{sha256_hash}   # exact DB lookup key
  agent_id: {uuid}                        # sub-agent instance ID
  tool_call_id: toolu_{id}               # links to workspace composer
  workspace: /path/to/workspace
  conversation_name: Name of parent conversation
  conversation_steps: 27                  # how many steps the sub-agent took
  duration_ms: 91793
roadmap:
  - related-spec.md                       # linked roadmap items (filled manually)
searches:
  - "search query 1"
  - "search query 2"
urls_fetched:
  - https://example.com/source1
  - https://example.com/source2
---

# Research Title

(full markdown research content)
```

### extract-research.py

`extract-research.py` (in this directory) scans Cursor's database for research-quality sub-agent outputs and saves them to `.research/`.

**Usage:**

```bash
# List new research (not yet saved)
python3 ~/dev/agentos-community/skills/cursor/extract-research.py --workspace .

# Save all new research to .research/
python3 ~/dev/agentos-community/skills/cursor/extract-research.py --workspace . --save

# Show all research including already-saved
python3 ~/dev/agentos-community/skills/cursor/extract-research.py --workspace . --all

# Extract a specific blob by hash prefix
python3 ~/dev/agentos-community/skills/cursor/extract-research.py --blob f0bc9dd6

# Filter by keyword
python3 ~/dev/agentos-community/skills/cursor/extract-research.py --filter "ontology"

# Custom output directory
python3 ~/dev/agentos-community/skills/cursor/extract-research.py --workspace . --save --research-dir /path/to/.research
```

**What qualifies as "research":** A Task tool result with at least 3 web searches, 3000+ chars of output, and 5+ conversation steps. These thresholds can be overridden with `--min-searches` and `--min-chars`.

### For AI agents: how to use this

1. **At session start**, if the workspace has a `sup.sh`, run it. It will report how many new research reports are available.
2. **To review past research**, read files in `.research/`. The front matter tells you exactly what was researched, when, and from which conversation.
3. **To find specific past research**, use `--filter` to search by keyword across all sub-agent research in the database.
4. **To recover a specific blob**, use `--blob {hash_prefix}` to extract the full text of any sub-agent output. The `blob_key` in front matter gives you the exact hash.
5. **After completing significant web research** via Task sub-agents, run the extraction script with `--save` to capture the new research before it gets lost.
6. **To query the database directly** (for custom analysis), open `state.vscdb` read-only with sqlite3 and query `cursorDiskKV` for `agentKv:blob:*` keys.
