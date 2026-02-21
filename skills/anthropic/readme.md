---
id: anthropic
name: Anthropic
description: Claude AI models via Anthropic Messages API
icon: icon.svg
color: "#000000"

website: https://www.anthropic.com
privacy_url: https://www.anthropic.com/privacy
terms_url: https://www.anthropic.com/terms-of-service

auth:
  type: api_key
  header: x-api-key
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

  # Claude 4
  - id: claude-4-opus-20250514
    types: [model]
    name: Claude 4 Opus
    data:
      provider: anthropic
      model_type: llm
      released: "2025-05-14"
      api_id: claude-opus-4-5
      context_window: 200000
      capabilities: [vision, tool_use, extended_thinking, caching, streaming]
      cost:
        input_per_million: 15.00
        output_per_million: 75.00
        cache_write_per_million: 18.75
        cache_read_per_million: 1.50
    relationships:
      - role: published_by
        to: anthropic-inc

  - id: claude-4-sonnet-20250514
    types: [model]
    name: Claude 4 Sonnet
    data:
      provider: anthropic
      model_type: llm
      released: "2025-05-14"
      api_id: claude-sonnet-4-5
      context_window: 200000
      capabilities: [vision, tool_use, extended_thinking, caching, streaming]
      cost:
        input_per_million: 3.00
        output_per_million: 15.00
        cache_write_per_million: 3.75
        cache_read_per_million: 0.30
    relationships:
      - role: published_by
        to: anthropic-inc

  # Claude 3.5
  - id: claude-3-5-haiku-20241022
    types: [model]
    name: Claude 3.5 Haiku
    data:
      provider: anthropic
      model_type: llm
      released: "2024-10-22"
      api_id: claude-3-5-haiku-20241022
      context_window: 200000
      capabilities: [vision, tool_use, caching, streaming]
      cost:
        input_per_million: 0.80
        output_per_million: 4.00
        cache_write_per_million: 1.00
        cache_read_per_million: 0.08
    relationships:
      - role: published_by
        to: anthropic-inc

  - id: claude-3-5-sonnet-20241022
    types: [model]
    name: Claude 3.5 Sonnet
    data:
      provider: anthropic
      model_type: llm
      released: "2024-10-22"
      api_id: claude-3-5-sonnet-20241022
      context_window: 200000
      capabilities: [vision, tool_use, caching, streaming]
      cost:
        input_per_million: 3.00
        output_per_million: 15.00
        cache_write_per_million: 3.75
        cache_read_per_million: 0.30
    relationships:
      - role: published_by
        to: anthropic-inc

instructions: |
  Claude models via the Anthropic API.

  Available models:
  - claude-4-opus: Most capable, slowest, highest cost ($15/M input, $75/M output)
  - claude-4-sonnet: Great balance ($3/M input, $15/M output)
  - claude-3.5-haiku: Fast, cheap, good enough for most tasks ($0.80/M input, $4/M output)

  For agent jobs, default to claude-3.5-haiku unless the task needs stronger reasoning.
  Most research, summarization, and classification work great with Haiku.

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
        messages: .params.messages
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

# Anthropic

Claude AI models via the [Anthropic Messages API](https://docs.anthropic.com/messages).

## Setup

1. Get your API key from https://console.anthropic.com/settings/keys
2. Add credential in AgentOS Settings → Skills → Anthropic

## Models

| Model | Best For | Cost |
|-------|----------|------|
| `claude-4-opus` | Complex reasoning, coding, math | $15/M in, $75/M out |
| `claude-4-sonnet` | Balance of capability and speed | $3/M in, $15/M out |
| `claude-3.5-haiku` | Speed, cost, most tasks | $0.80/M in, $4/M out |

For agent jobs: start with Haiku. Upgrade to Sonnet if you hit accuracy limits.

## Usage

Call the `chat` utility to send a message to Claude:

```bash
curl -X POST http://localhost:3456/api/skills/anthropic/chat \
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
curl -X POST http://localhost:3456/api/skills/anthropic/chat \
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
curl -X POST http://localhost:3456/api/skills/anthropic/chat \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-haiku-20241022",
    "system": "You are a helpful assistant. Keep responses concise.",
    "messages": [...]
  }'
```

## Cost Optimization

- Use Haiku for: summaries, classifications, simple Q&A, research
- Use Sonnet for: complex reasoning, multi-step tasks, code generation
- Set `temperature: 0` for deterministic agent tasks (default for jobs)
- Set `max_tokens` based on expected output to avoid over-generation
