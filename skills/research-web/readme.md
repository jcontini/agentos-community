---
id: research-web
name: Research Web
description: AI agent that researches questions by searching and reading the web
icon: icon.svg
color: "#2563EB"

agent:
  intelligence: claude-desktop/claude-haiku-4-5
  system_prompt: |
    You are a research agent. Your job is to thoroughly answer questions by searching
    the web and reading relevant pages.

    Process:
    1. Search for the question using webpage.search
    2. Read the most relevant results using webpage.read
    3. Synthesize what you found into a clear, accurate answer
    4. Always cite your sources (include URLs)

    Be thorough but concise. If the first search isn't sufficient, search again with
    different terms. Prefer primary sources over summaries.
  tools:
    - webpage.search
    - webpage.read
  max_iterations: 10

credits:
  - entity: webpage
    operations: [search, read]
    relationship: needs

---

# Research Web

An AI agent that answers questions by searching and reading the web. Runs as a background
job — creates a conversation entity with the full reasoning trace.

## Usage

```
use({ skill: "research-web", tool: "research", params: {
  prompt: "What are the tradeoffs between SQLite and PostgreSQL for a local-first app?"
}})
```

Returns a job ID and conversation ID. The agent runs asynchronously — check the job
entity for status, or read the conversation to see the full reasoning trace.

## Requirements

Needs at least one skill with `webpage.search` and one with `webpage.read` configured.
Exa works for both. Brave works for search.

## Cost

Uses Claude 3.5 Haiku by default (~$0.024 per research task of 10 iterations).
