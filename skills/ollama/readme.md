---
id: ollama
name: Ollama
description: Local AI models running on your machine via Ollama
icon: icon.svg
color: "#0F172A"
platforms: [macos, linux, windows]

website: https://ollama.com
privacy_url: https://ollama.com/privacy
terms_url: https://ollama.com/terms

auth: none

connects_to: ollama-daemon

seed:
  - id: ollama-inc
    types: [organization]
    name: Ollama
    data:
      type: company
      url: https://ollama.com

  - id: ollama-daemon
    types: [software]
    name: Ollama Local API
    data:
      software_type: api
      url: https://ollama.com
      platforms: [macos, linux, windows]
    relationships:
      - role: offered_by
        to: ollama-inc

instructions: |
  Ollama runs models locally with no API key.

  Requirements:
  - Ollama installed and running locally
  - At least one model pulled, e.g. `ollama pull llama3.2`

  For private or offline jobs, prefer Ollama.

utilities:
  chat:
    description: Send a chat request to the local Ollama API
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
        description: "Local model name (e.g., llama3.2, qwen2.5-coder:7b)"
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
        description: "Maximum tokens to generate (num_predict)"
      temperature:
        type: number
        default: 0
        description: "Sampling temperature (0 = deterministic for agents)"
      system:
        type: string
        description: "Optional system prompt"
    rest:
      method: POST
      url: http://localhost:11434/api/chat
      body:
        model: .params.model
        messages: 'if .params.system then ([{role: "system", content: .params.system}] + .params.messages) else .params.messages end'
        tools: '(.params.tools // []) | map({type: "function", function: {name: .name, description: (.description // ""), parameters: (.input_schema // {type: "object", properties: {}})}})'
        stream: false
        options:
          temperature: '.params.temperature // 0'
          num_predict: '.params.max_tokens // 4096'
      response:
        transform: '{content: (.message.content // null), tool_calls: [(.message.tool_calls // [])[] | {id: (.id // .function.name // "tool_call"), name: .function.name, input: (((.function.arguments // "{}") | (if type == "string" then (fromjson? // {}) else . end)) // {})}], stop_reason: (if .done_reason == "tool_calls" then "tool_use" elif .done_reason == "length" then "max_tokens" else "end_turn" end), usage: {input_tokens: (.prompt_eval_count // 0), output_tokens: (.eval_count // 0)}}'
        mapping:
          content: .content
          tool_calls: .tool_calls
          stop_reason: .stop_reason
          usage: .usage

---

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
