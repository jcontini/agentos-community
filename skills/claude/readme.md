---
id: claude
name: Claude Desktop
description: Anthropic's AI assistant desktop app with native MCP support
icon: icon.png
color: "#D97757"
platforms: [macos, windows]

website: https://claude.ai

auth: none

instructions: >
  You are running in the Claude Desktop app. MCP config lives at
  ~/Library/Application Support/Claude/claude_desktop_config.json.
  Restart Claude Desktop to reload config changes — no hot reload.
  If MCP tools aren't appearing, check that the config JSON is valid and restart.

connects_to: claude-desktop

seed:
  - id: claude-desktop
    types: [software]
    name: Claude Desktop
    data:
      software_type: ai_client
      url: https://claude.ai
      platforms: [macos, windows]
    relationships: []

testing:
  exempt:
    operations: Guide-only skill — no API operations
---

# Claude Desktop

Anthropic's AI assistant desktop app with native MCP support.

## Setup

1. Click **Install to Claude Desktop** in agentOS
2. Restart Claude Desktop to load the MCP configuration
3. Your apps will be available automatically

## Instructions for AI

You are running in the Claude Desktop app.

- MCP config: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Restart Claude Desktop to reload MCP config changes (no hot reload — full quit and reopen required)
- Claude Desktop does not have file editing tools — you work through conversation, not code changes
- If MCP tools aren't appearing, check that the config JSON is valid and restart Claude Desktop

## Tips for users

- **Artifacts**: Claude can create interactive artifacts (code, documents, diagrams) in the sidebar
- **Projects**: Group conversations with shared context using Projects
- **MCP tools**: After installing agentOS, tools appear automatically — no @mention needed, Claude will use them when relevant
- **Multiple MCP servers**: Claude Desktop supports multiple MCP server configs side by side in the same JSON file
