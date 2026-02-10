---
id: cursor
name: Cursor
description: AI-first code editor with MCP support
category: code
icon: icon.png
color: "#3B82F6"

platforms:
  macos:
    app_path: /Applications/Cursor.app
    config_path: ~/.cursor/mcp.json
  windows:
    app_path: "%LOCALAPPDATA%/Programs/Cursor/Cursor.exe"
    config_path: "%APPDATA%/Cursor/mcp.json"
  linux:
    app_path: /usr/share/cursor/cursor
    config_path: ~/.cursor/mcp.json
---

# Cursor

AI-first code editor with built-in MCP support.

## Setup

1. Click **Install to Cursor** in agentOS
2. Restart Cursor to load the MCP configuration
3. Your apps will be available automatically

## Instructions for AI

You are running in Cursor.

- MCP config: ~/.cursor/mcp.json
- To reload MCP config: rename ~/.cursor/mcp.json → mcp.json.bak → then back to mcp.json (triggers hot reload without restart)
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
