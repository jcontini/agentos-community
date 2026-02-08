---
id: whois
name: WHOIS
description: Domain lookups via system whois command
icon: icon.svg

auth:
  type: none

instructions: |
  Uses the system `whois` command for domain lookups. No API key required.
  
  **Capabilities:**
  - Look up domain registration info
  - Check if a domain is available
  
  **Note:** Output is raw WHOIS text. AI interprets the data.

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  domain.get:
    description: WHOIS lookup for a domain
    returns: void
    params:
      domain: { type: string, required: true, description: "Domain to look up (e.g. example.com)" }
    command:
      binary: whois
      args:
        - .params.domain
      timeout: 30

  domain.check:
    description: Check if a domain is available (via WHOIS)
    returns: void
    params:
      domain: { type: string, required: true, description: "Domain to check (e.g. example.com)" }
    command:
      binary: whois
      args:
        - .params.domain
      timeout: 15
---

# WHOIS

Uses the system `whois` command for domain lookups. No API key required.

## Setup

The `whois` command is pre-installed on macOS and most Linux distributions.

## Usage

```bash
# Look up a domain
curl -X POST http://localhost:3456/api/adapters/whois/domain.get \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "example.com"}'

# Check availability (same command, AI interprets "No match" as available)
curl -X POST http://localhost:3456/api/adapters/whois/domain.check \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "somecoolname.com"}'
```

## Notes

- Output is raw WHOIS text — AI interprets the structured data
- "No match" or "NOT FOUND" typically means available
- Some TLDs have rate limits on WHOIS queries
- Privacy-protected domains show redacted registrant info
