# Cursor

AI-first code editor with built-in MCP support.

## Setup

1. Click **Install to Cursor** in agentOS
2. Restart Cursor to load the MCP configuration
3. Your apps will be available automatically

MCP config locations:
- macOS/Linux: `~/.cursor/mcp.json`
- Windows: `%APPDATA%/Cursor/mcp.json`

**Use the release binary** for the agentOS MCP command (`target/release/agentos`). `restart.sh` only rebuilds release by default, so the debug binary goes stale.

## Instructions for AI

You are running in Cursor.

- MCP config: `~/.cursor/mcp.json` (user-level; applies to all projects)
- To reload MCP config: `cp ~/.cursor/mcp.json ~/.cursor/mcp.json.nudge && sleep 0.5 && mv ~/.cursor/mcp.json.nudge ~/.cursor/mcp.json` — triggers hot reload without restarting Cursor. Use `cp` not `mv` so the original is never missing if interrupted.
- If any tools are disconnected, reload MCP config using the command above, then retry.
- To install or remove the agentOS MCP entry: use `run({ skill: "cursor", tool: "install_mcp" })` / `uninstall_mcp`.

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

## MCP Configuration

The `install_mcp` and `uninstall_mcp` operations manage the agentOS MCP entry in a client's config file.

```js
// Install (auto-detects binary path)
run({ skill: "cursor", tool: "install_mcp" })

// Install with explicit path
run({ skill: "cursor", tool: "install_mcp", params: { binary_path: "/Users/you/dev/agentos/target/release/agentos" } })

// Remove
run({ skill: "cursor", tool: "uninstall_mcp" })
```

**Binary path auto-detection** (in order):
1. Running engine PID (`~/.agentos/engine.pid`) → `lsof` to read the actual binary path
2. Existing `~/.cursor/mcp.json` → reuse the current `command` value
3. `which agentos`
4. Fails with an actionable error if none found

**Use the release binary** in production (`target/release/agentos`). Debug builds go stale between rebuilds; `restart.sh` only rebuilds release by default. The auto-detection picks up whichever binary is currently running — if you just ran `restart.sh`, that's the release build.

The config is written atomically (temp file + rename) so a crash mid-write never leaves `mcp.json` missing or truncated.

---

## Syncing Sessions to the Graph

Cursor sessions become `session` entities on the graph with `client: "cursor"`, a `workspace` slug, and the full conversation transcript as searchable body content.

**Two data sources:**

1. **JSONL transcripts** (`~/.cursor/projects/*/agent-transcripts/*.jsonl`) — Recent sessions. Cursor started writing these around Feb 2026. Fast to read (sub-second). This is what `list_sessions` reads.

2. **SQLite databases** (`~/Library/Application Support/Cursor/User/workspaceStorage/*/state.vscdb` + `globalStorage/state.vscdb`) — Full history going back months. Composer metadata lives in each workspace DB; message blobs live in the 13+ GB global DB. This is what `backfill_session` reads.

**Recommended workflow:**

```
# One-time: import full history (all workspaces, ~7 seconds)
run({ skill: "cursor", tool: "backfill_session" })

# Or import just one workspace
run({ skill: "cursor", tool: "backfill_session", params: { workspace: "/Users/joe/dev/agentos" } })

# Ongoing: session.list runs automatically via entity fan-out when anyone calls
list({ type: "session" })
```

After import, all sessions are FTS5-searchable:
```
search({ query: "Langfuse pipeline", types: ["session"] })
```

**Stats:** Run `python3 cursor.py --stats` to see how many sessions are available across both sources and all workspaces before importing. (The old `list-conversations.py` still exists for standalone use but skill operations now use `cursor.py`.)

**Deduplication:** Sessions are deduplicated by UUID (remote_id). Safe to run backfill multiple times — existing sessions won't be duplicated.

---

## Cursor Tool Definitions

Cursor's own tool schemas live inside its bundled extensions:

```
/Applications/Cursor.app/Contents/Resources/app/extensions/
  cursor-agent/dist/main.js       (~2.9MB) — agent orchestration
  cursor-agent-exec/dist/main.js  (~4.1MB) — tool execution engine
```

The `cursor-agent-exec` bundle contains the core file editing tools. Tool constants found there: `READ_FILE`, `EDIT_FILE`, `DELETE_FILE`, `LIST_DIR`, `WEB_SEARCH` (plus lowercase equivalents: `read_file`, `edit_file`, `delete_file`, `run_terminal`, `web_search`).

To extract tool-related sections from these files:
```bash
# List all tool constants
grep -oE '\b(READ_FILE|WRITE_FILE|EDIT_FILE|CREATE_FILE|DELETE_FILE|LIST_DIR|RUN_TERMINAL|GREP|WEB_SEARCH|STR_REPLACE)\b' \
  /Applications/Cursor.app/Contents/Resources/app/extensions/cursor-agent-exec/dist/main.js | sort -u

# Find tool schemas (look for name + description + parameters patterns)
python3 -c "
import re
with open('/Applications/Cursor.app/Contents/Resources/app/extensions/cursor-agent-exec/dist/main.js', 'r', errors='ignore') as f:
    content = f.read()
# search for your pattern here
"
```

The **full tool list I have access to in Cursor** (as of early 2026):
`Read`, `Write`, `StrReplace`, `Delete`, `Shell`, `Grep`, `Glob`, `SemanticSearch`, `ReadLints`, `EditNotebook`, `TodoWrite`, `GenerateImage`, `AskQuestion`, `Task`, `SwitchMode`, `WebSearch`, `WebFetch`, `CallMcpTool`, `FetchMcpResource`

These map to file operations: Read/Write/StrReplace/Delete cover all CRUD on files. Grep + Glob cover search and find. Shell covers anything else.

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

### Research extraction

The `pull_document` skill operation and the standalone `extract-research.py` script both scan Cursor's database for research-quality sub-agent outputs.

**Via skill (imports into graph):**
```js
run({ skill: "cursor", tool: "pull_document" })
```

**Standalone script (saves to `.research/` directory):**
```bash
# List new research (not yet saved)
python3 ./extract-research.py --workspace .

# Save all new research to .research/
python3 ./extract-research.py --workspace . --save

# Show all research including already-saved
python3 ./extract-research.py --workspace . --all

# Extract a specific blob by hash prefix
python3 ./extract-research.py --blob f0bc9dd6

# Filter by keyword
python3 ./extract-research.py --filter "ontology"

# Custom output directory
python3 ./extract-research.py --workspace . --save --research-dir /path/to/.research
```

**What qualifies as "research":** A Task tool result with at least 3 web searches, 3000+ chars of output, and 5+ conversation steps. These thresholds can be overridden with `--min-searches` and `--min-chars`.

### For AI agents: how to use this

1. **At session start**, if the workspace has a `sup.sh`, run it. It will report how many new research reports are available.
2. **To review past research**, read files in `.research/`. The front matter tells you exactly what was researched, when, and from which conversation.
3. **To find specific past research**, use `--filter` to search by keyword across all sub-agent research in the database.
4. **To recover a specific blob**, use `--blob {hash_prefix}` to extract the full text of any sub-agent output. The `blob_key` in front matter gives you the exact hash.
5. **After completing significant web research** via Task sub-agents, run the extraction script with `--save` to capture the new research before it gets lost.
6. **To query the database directly** (for custom analysis), open `state.vscdb` read-only with sqlite3 and query `cursorDiskKV` for `agentKv:blob:*` keys.
