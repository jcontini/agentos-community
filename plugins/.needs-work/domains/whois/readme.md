---
id: whois
name: WHOIS
description: Domain lookups via system whois command
icon: icon.svg
tags: [web, domain, dns, lookup]

auth:
  type: none

# Action implementations (merged from mapping.yaml)
actions:
  whois:
    operation: read
    label: "WHOIS lookup"
    command:
      binary: whois
      args:
        - "{{params.domain}}"
      timeout: 30

  check:
    operation: read
    label: "Check availability"
    command:
      binary: whois
      args:
        - "{{params.domain}}"
      timeout: 15
---

# WHOIS

Uses the system `whois` command for domain lookups. No API key required.

## Setup

The `whois` command is pre-installed on macOS and most Linux distributions.

## Notes

- Output is raw WHOIS text - AI interprets the structured data
- Some TLDs have rate limits on WHOIS queries
- Privacy-protected domains will show redacted registrant info
