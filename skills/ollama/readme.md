# Ollama

Ollama lets AgentOS run intelligence locally, offline, and without API costs.

## Setup

1. Install Ollama: https://ollama.com/download
2. Pull a model, for example:

```bash
ollama pull llama3.2
```

3. Ensure Ollama daemon is running (`http://localhost:11434`)

## Usage

```bash
curl -X POST http://localhost:3456/api/skills/ollama/chat \
  -H "X-Agent: cursor" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [
      { "role": "user", "content": "Give me three bullet points on local-first apps." }
    ]
  }'
```

The response is normalized to the canonical `chat` output:
`content`, `tool_calls`, `stop_reason`, and `usage`.
