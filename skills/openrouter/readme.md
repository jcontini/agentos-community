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
