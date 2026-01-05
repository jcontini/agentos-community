---
id: exa
name: Exa
description: Semantic web search and content extraction
icon: icon.png
color: "#5436DA"

website: https://exa.ai
privacy_url: https://exa.ai/privacy
terms_url: https://exa.ai/terms

auth:
  type: api_key
  header: x-api-key
  label: API Key
  help_url: https://dashboard.exa.ai/api-keys

instructions: |
  Exa-specific notes:
  - Neural search finds content by meaning, not just keywords
  - Fast: typically under 1 second per request
  - Use for research, concepts, "how to" queries
---

# Exa

Semantic web search and content extraction. Neural search finds content by meaning, not just keywords.

## Setup

1. Get your API key from https://dashboard.exa.ai/api-keys
2. Add credential in AgentOS Settings → Providers → Exa

## Features

- Neural/semantic search
- Fast content extraction
- Find similar pages
- Relevance scoring

## When to Use

- Research and concepts
- "How to" queries
- Finding related content
- Fast searches (default provider)
