---
id: anthropic-api
name: Anthropic API
description: Claude AI models via Anthropic Messages API
color: "#000000"
website: "https://www.anthropic.com"
privacy_url: "https://www.anthropic.com/privacy"
terms_url: "https://www.anthropic.com/terms-of-service"

connections:
  api:
    base_url: https://api.anthropic.com/v1
    auth:
      type: api_key
      header:
        x-api-key: .auth.key
    label: API Key
    help_url: https://console.anthropic.com/settings/keys
---

# Anthropic API

Claude AI models via the [Anthropic Messages API](https://docs.anthropic.com/messages).

## Setup

1. Get your API key from https://console.anthropic.com/settings/keys
2. Add credential in AgentOS Settings → Skills → Anthropic API

## Models

Use `list_models` to discover available models:

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
