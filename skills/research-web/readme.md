# Research Web

An AI agent that answers questions by searching and reading the web. Runs as a background
job — creates a conversation entity with the full reasoning trace.

## Usage

```
run({ skill: "research-web", tool: "research", params: {
  prompt: "What are the tradeoffs between SQLite and PostgreSQL for a local-first app?"
}})
```

Returns a job ID and conversation ID. The agent runs asynchronously — check the job
entity for status, or read the conversation to see the full reasoning trace.

## Requirements

Requires the runtime to expose `webpage.search` and `webpage.read` (via whatever integrations are connected). The agent config above references those operations by name, not by a specific provider.

## Cost

Uses Claude 3.5 Haiku by default (~$0.024 per research task of 10 iterations).
