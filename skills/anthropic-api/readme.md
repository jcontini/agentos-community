---
id: anthropic-api
name: Anthropic API
description: Claude AI models via Anthropic Messages API
icon: icon.svg
color: "#000000"

website: https://www.anthropic.com
privacy_url: https://www.anthropic.com/privacy
terms_url: https://www.anthropic.com/terms-of-service

auth:
  header: { x-api-key: "{token}" }
  label: API Key
  help_url: https://console.anthropic.com/settings/keys

connects_to: anthropic-api

seed:
  - id: anthropic-inc
    types: [organization]
    name: Anthropic
    data:
      type: company
      url: https://www.anthropic.com
      founded: "2021"

  - id: anthropic-api
    types: [software]
    name: Anthropic Messages API
    data:
      software_type: api
      url: https://console.anthropic.com
      launched: "2023"
      platforms: [api]
    relationships:
      - role: offered_by
        to: anthropic-inc

transformers:
  model:
    terminology: Model
    mapping:
      api_id: .id
      title: .display_name
      released: .created_at
      provider: '"anthropic"'
      model_type: '"llm"'

operations:
  model.list:
    description: List available Claude models from Anthropic
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

instructions: |
  Claude models via the Anthropic API.

  Use model.list to discover available models — don't hardcode model IDs.
  Models change frequently; the API always has the latest.

  For agent jobs, pick the smallest model that works. Upgrade only when needed.

  Tool use: The API supports tool_calls for function calling. Pass tool definitions
  in the `tools` parameter. The model returns `stop_reason: "tool_use"` when it wants
  to call a tool.

utilities:
  chat:
    description: Send a chat completion request to Claude (Anthropic Messages API)
    returns:
      content:
        type: string
        description: Text response from Claude (null if only tool calls)
      tool_calls:
        type: array
        description: Tool calls the model wants to make
      stop_reason:
        type: string
        enum: [end_turn, tool_use, max_tokens]
      usage:
        type: object
        description: Token usage statistics
    params:
      model:
        type: string
        required: true
        description: "Model ID (e.g., claude-3-5-haiku-20241022, claude-4-sonnet-20250514)"
      messages:
        type: array
        required: true
        description: "Array of message objects with role and content"
      tools:
        type: array
        description: "Optional array of tool definitions for function calling"
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
      url: https://api.anthropic.com/v1/messages
      headers:
        anthropic-version: '"2023-06-01"'
      body:
        model: .params.model
        messages: 'def to_anthropic_msg: if .role == "assistant" and .tool_calls then {role: "assistant", content: ([if .content then {type: "text", text: .content} else empty end] + [.tool_calls[] | {type: "tool_use", id: .id, name: .name, input: .input}])} elif .role == "tool" then {role: "user", content: [{type: "tool_result", tool_use_id: .tool_call_id, content: .content}]} else . end; [.params.messages[] | to_anthropic_msg]'
        tools: .params.tools
        max_tokens: '.params.max_tokens // 4096'
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

# Anthropic API

Claude AI models via the [Anthropic Messages API](https://docs.anthropic.com/messages).

## Setup

1. Get your API key from https://console.anthropic.com/settings/keys
2. Add credential in AgentOS Settings → Skills → Anthropic API

## Models

Use `model.list` to discover available models:

```bash
curl http://localhost:3456/mem/models?skill=anthropic-api -H "X-Agent: cursor"
```

Models are pulled from the Anthropic API and stored as entities on the graph. Don't hardcode model IDs — query the graph for the latest.

## Usage

Call the `chat` utility to send a message to Claude:

```bash
curl -X POST http://localhost:3456/api/skills/anthropic-api/chat \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "messages": [
      {
        "role": "user",
        "content": "What is the capital of France?"
      }
    ]
  }'
```

Response:
```json
{
  "content": "The capital of France is Paris.",
  "tool_calls": [],
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 12,
    "output_tokens": 8
  }
}
```

## Tool Use (Function Calling)

Pass tool definitions to enable function calling:

```bash
curl -X POST http://localhost:3456/api/skills/anthropic-api/chat \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "messages": [
      {
        "role": "user",
        "content": "What is the weather in San Francisco?"
      }
    ],
    "tools": [
      {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "input_schema": {
          "type": "object",
          "properties": {
            "location": {"type": "string"}
          },
          "required": ["location"]
        }
      }
    ]
  }'
```

If the model wants to call a tool, the response will have:
```json
{
  "content": null,
  "tool_calls": [
    {
      "id": "toolu_01...",
      "name": "get_weather",
      "input": {"location": "San Francisco"}
    }
  ],
  "stop_reason": "tool_use"
}
```

## System Prompt

Pass a system prompt for context:

```bash
curl -X POST http://localhost:3456/api/skills/anthropic-api/chat \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "system": "You are a helpful assistant. Keep responses concise.",
    "messages": [...]
  }'
```

## Tips

- Start with the smallest model that works — upgrade only if needed
- Set `temperature: 0` for deterministic agent tasks (default for jobs)
- Set `max_tokens` based on expected output to avoid over-generation
