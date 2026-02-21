---
id: openrouter
name: OpenRouter
description: Unified AI gateway for models across providers via one API
icon: icon.svg
color: "#111827"

website: https://openrouter.ai
privacy_url: https://openrouter.ai/privacy
terms_url: https://openrouter.ai/terms

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: API Key
  help_url: https://openrouter.ai/keys

connects_to: openrouter-api

seed:
  - id: openrouter-inc
    types: [organization]
    name: OpenRouter
    data:
      type: company
      url: https://openrouter.ai

  - id: openrouter-api
    types: [software]
    name: OpenRouter API
    data:
      software_type: api
      url: https://openrouter.ai
      platforms: [api]
    relationships:
      - role: offered_by
        to: openrouter-inc

instructions: |
  OpenRouter provides one API key for many model providers.

  Model IDs are provider-qualified, for example:
  - anthropic/claude-3.5-haiku
  - openai/gpt-4o-mini
  - meta-llama/llama-3.1-70b-instruct

  For agent jobs, start with cheaper models and upgrade only when needed.

utilities:
  chat:
    description: Send a chat completion request through OpenRouter
    returns:
      content:
        type: string
        description: Text response from the model (null if tool calls only)
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
        description: "Model ID (e.g., anthropic/claude-3.5-haiku, openai/gpt-4o-mini)"
      messages:
        type: array
        required: true
        description: "Array of message objects with role and content"
      tools:
        type: array
        description: "Optional canonical tool definitions ({name, description, input_schema})"
      max_tokens:
        type: integer
        default: 4096
        description: "Maximum tokens to generate"
      temperature:
        type: number
        default: 0
        description: "Sampling temperature (0 = deterministic for agents)"
      system:
        type: string
        description: "Optional system prompt"
    rest:
      method: POST
      url: https://openrouter.ai/api/v1/chat/completions
      body:
        model: .params.model
        messages: 'if .params.system then ([{role: "system", content: .params.system}] + .params.messages) else .params.messages end'
        tools: '(.params.tools // []) | map({type: "function", function: {name: .name, description: (.description // ""), parameters: (.input_schema // {type: "object", properties: {}})}})'
        max_tokens: '.params.max_tokens // 4096'
        temperature: '.params.temperature // 0'
      response:
        transform: '{content: (.choices[0].message.content // null), tool_calls: [(.choices[0].message.tool_calls // [])[] | {id: .id, name: .function.name, input: (((.function.arguments // "{}") | (if type == "string" then (fromjson? // {}) else . end)) // {})}], stop_reason: (if .choices[0].finish_reason == "tool_calls" then "tool_use" elif .choices[0].finish_reason == "length" then "max_tokens" else "end_turn" end), usage: {input_tokens: (.usage.prompt_tokens // 0), output_tokens: (.usage.completion_tokens // 0)}}'
        mapping:
          content: .content
          tool_calls: .tool_calls
          stop_reason: .stop_reason
          usage: .usage

---

# OpenRouter

OpenRouter lets AgentOS access models from multiple providers using one API key and one `chat` interface.

## Setup

1. Create an API key at https://openrouter.ai/keys
2. Add credential in AgentOS Settings -> Skills -> OpenRouter

## Usage

Use `chat` with a provider-qualified model ID:

```bash
curl -X POST http://localhost:3456/api/skills/openrouter/chat \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      { "role": "user", "content": "Summarize this in one sentence: AgentOS is local-first." }
    ]
  }'
```

The response is normalized to AgentOS' canonical shape:
`content`, `tool_calls`, `stop_reason`, and `usage`.
