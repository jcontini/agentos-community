---
id: claude-desktop
name: Claude Desktop
description: Claude AI via your Claude Desktop subscription — calls billed to your Pro/Max plan
icon: icon.png
color: "#D97757"
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

adapters:
  model:
    id: .id
    name: .display_name
    datePublished: .created_at
    data.provider: '"anthropic"'
    data.model_type: '"llm"'

  conversation:
    id: .id
    name: .name
    text: .last_message
    content: .transcript
    datePublished: .last_message_at
    data.client: '"claude-desktop"'
    data.workspace: .workspace
    data.user_turns: .user_turns
    data.message_count: .message_count

operations:
  list_models:
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

  list_conversations:
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
      args: ["-l", "-c", 'PARAM_WORKSPACE="$1"; python3 ./list-sessions.py --json --workspace "${PARAM_WORKSPACE}" 2>/dev/null', "--", ".params.workspace"]
      working_dir: .
      timeout: 30

  search_conversations:
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
      args: ["-l", "-c", 'PARAM_QUERY="$1"; PARAM_WORKSPACE="$2"; python3 ./list-sessions.py --json --query "${PARAM_QUERY}" --workspace "${PARAM_WORKSPACE}" 2>/dev/null', "--", ".params.query", ".params.workspace"]
      working_dir: .
      timeout: 30

  get_conversation:
    description: Get a Claude Code session by UUID with full conversation transcript
    returns: conversation
    params:
      id:
        type: string
        required: true
        description: Session UUID
    command:
      binary: bash
      args: ["-l", "-c", 'PARAM_ID="$1"; python3 ./list-sessions.py --json --id "${PARAM_ID}" 2>/dev/null', "--", ".params.id"]
      working_dir: .
      timeout: 15

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
---

# Claude Desktop

Connect Claude AI using your existing Claude Desktop subscription (Pro or Max). Calls are billed to your plan — no separate API account or key needed.

## How it works

AgentOS reads the OAuth token that Claude Desktop stores in its encrypted local config (`~/Library/Application Support/Claude/config.json`), decrypts it using your macOS Keychain, and uses it to call the Anthropic Messages API directly. The token is refreshed automatically when it expires.

## Requirements

- Claude Desktop app installed and signed in
- Claude Pro or Max plan (free tier may not support API access)

## Session History

Claude Code (the agentic CLI that runs inside Claude Desktop) stores conversation transcripts locally at `~/.claude/projects/{workspace}/`. The `list_conversations`, `search_conversations`, and `get_conversation` operations read these files directly — no credentials or network access needed.

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
