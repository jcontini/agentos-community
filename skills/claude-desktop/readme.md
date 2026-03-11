---
id: claude-desktop
name: Claude Desktop
description: Claude AI via your Claude Desktop subscription — calls billed to your Pro/Max plan
icon: icon.png
color: "#D97757"
platforms: [macos]

website: https://claude.ai
privacy_url: https://www.anthropic.com/privacy
terms_url: https://www.anthropic.com/terms-of-service

# TODO: Phase 2/3 — re-implement via steps executor (keychain → crypto → json parse)
# The old safestorage resolver extracted OAuth tokens from Claude's encrypted config.
# For now, auth is disabled until the steps/keychain/crypto executors exist.
auth:
  header:
    Authorization: "Bearer {token}"
    anthropic-version: "2023-06-01"
    anthropic-beta: "oauth-2025-04-20"
  label: Claude Desktop subscription
  help_url: https://claude.ai

connects_to: claude-desktop-app

seed:
  - id: claude-desktop-app
    types: [software]
    name: Claude Desktop
    data:
      software_type: ai_client
      url: https://claude.ai
      platforms: [macos, windows]
    relationships:
      - role: offered_by
        to: anthropic-inc

  - id: anthropic-inc
    types: [organization]
    name: Anthropic
    data:
      type: company
      url: https://www.anthropic.com
      founded: "2021"

transformers:
  model:
    terminology: Model
    mapping:
      api_id: .id
      title: .display_name
      released: .created_at
      provider: '"anthropic"'
      model_type: '"llm"'

  conversation:
    terminology: Session
    mapping:
      id: .id
      name: .name
      client: '"claude-desktop"'
      last_message: .last_message
      last_message_at: .last_message_at
      data.workspace: .workspace
      data.user_turns: .user_turns
      data.message_count: .message_count
      content: .transcript

operations:
  model.list:
    description: List available Claude models (via your Claude Desktop subscription)
    returns: model[]
    rest:
      method: GET
      url: https://api.anthropic.com/v1/models
      query:
        limit: '"1000"'
      headers:
        anthropic-version: '"2023-06-01"'
      response:
        root: /data

  conversation.list:
    description: >
      List Claude Code sessions from local JSONL transcripts in ~/.claude/projects/.
      Claude Code is the CLI that runs inside Claude Desktop for agentic coding tasks.
      Sessions are stored locally and available without credentials.
    returns: conversation[]
    params:
      workspace:
        type: string
        description: Filter to sessions in a specific workspace path (e.g. /Users/joe/dev/myproject)
    command:
      binary: bash
      args: ["-l", "-c", "python3 ~/dev/agentos-community/skills/claude-desktop/list-sessions.py --json --workspace '{{params.workspace}}' 2>/dev/null"]
      timeout: 30

  conversation.search:
    description: >
      Search Claude Code session history by content.
      Searches through the full text of all local session transcripts.
    returns: conversation[]
    params:
      query:
        type: string
        required: true
        description: Text to search for in session content
      workspace:
        type: string
        description: Optionally limit search to a specific workspace path
    command:
      binary: bash
      args: ["-l", "-c", "python3 ~/dev/agentos-community/skills/claude-desktop/list-sessions.py --json --query '{{params.query}}' --workspace '{{params.workspace}}' 2>/dev/null"]
      timeout: 30

  conversation.get:
    description: Get a Claude Code session by UUID with full conversation transcript
    returns: conversation
    params:
      id:
        type: string
        required: true
        description: Session UUID
    command:
      binary: bash
      args: ["-l", "-c", "python3 ~/dev/agentos-community/skills/claude-desktop/list-sessions.py --json --id '{{params.id}}' 2>/dev/null"]
      timeout: 15

instructions: |
  Claude AI via your Claude Desktop subscription. Calls are billed to your Pro/Max plan —
  not a separate API account.

  Use model.list to discover available models — don't hardcode model IDs.
  The token is read directly from Claude Desktop's encrypted config — no API key needed.
  If Claude Desktop is not installed or not signed in, this skill will fail.

  Session history is stored locally in ~/.claude/projects/ as JSONL files — no credentials
  needed to read it. Use conversation.list to browse, conversation.search to find by content,
  conversation.get to retrieve a full transcript by UUID.

utilities:
  chat:
    description: Send a message to Claude (billed to your Claude Desktop Pro/Max subscription)
    returns:
      content:
        type: string
        description: Text response from Claude (null if tool calls only)
      tool_calls:
        type: array
        description: Tool calls the model wants to make
      stop_reason:
        type: string
        enum: [end_turn, tool_use, max_tokens]
      usage:
        type: object
        description: Token usage (input_tokens, output_tokens)
    params:
      model:
        type: string
        required: true
        description: "Model ID (e.g., claude-3-haiku-20240307, claude-sonnet-4-5)"
      messages:
        type: array
        required: true
        description: "Array of {role, content} objects"
      tools:
        type: array
        description: "Tool definitions for function calling"
      max_tokens:
        type: integer
        default: 1024
        description: "Maximum tokens to generate"
      temperature:
        type: number
        default: 0
        description: "Sampling temperature (0 = deterministic)"
      system:
        type: string
        description: "Optional system prompt"
    rest:
      method: POST
      url: https://api.anthropic.com/v1/messages
      body:
        model: .params.model
        messages: .params.messages
        tools: .params.tools
        max_tokens: '.params.max_tokens // 1024'
        temperature: '.params.temperature // 0'
        system: .params.system
      response:
        transform: '{content: (.content[0].text // null), tool_calls: [.content[] | select(.type == "tool_use") | {id: .id, name: .name, input: .input}], stop_reason: .stop_reason, usage: .usage}'
        mapping:
          content: .content
          tool_calls: .tool_calls
          stop_reason: .stop_reason
          usage: .usage

testing:
  exempt:
    operations: Local command skill — reads ~/.claude/projects/ JSONL files, tested manually
    utilities: Requires live Claude Desktop OAuth token — tested manually
---

# Claude Desktop

Connect Claude AI using your existing Claude Desktop subscription (Pro or Max). Calls are billed to your plan — no separate API account or key needed.

## How it works

AgentOS reads the OAuth token that Claude Desktop stores in its encrypted local config (`~/Library/Application Support/Claude/config.json`), decrypts it using your macOS Keychain, and uses it to call the Anthropic Messages API directly. The token is refreshed automatically when it expires.

## Requirements

- Claude Desktop app installed and signed in
- Claude Pro or Max plan (free tier may not support API access)

## Session History

Claude Code (the agentic CLI that runs inside Claude Desktop) stores conversation transcripts locally at `~/.claude/projects/{workspace}/`. The `session.list`, `session.search`, and `session.get` operations read these files directly — no credentials or network access needed.

**What's stored locally:**
- Claude Code (CLI) sessions — full transcripts in `~/.claude/projects/`
- Session metadata in `~/Library/Application Support/Claude/claude-code-sessions/`

**What's NOT stored locally:**
- Claude.ai web chat history — that lives server-side only

## MCP Setup

To add AgentOS tools to Claude Desktop's MCP config:

1. Click **Install to Claude Desktop** in agentOS
2. Restart Claude Desktop (full quit + reopen)
3. Tools appear automatically — no @mention needed
