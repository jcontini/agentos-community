---
id: domainr
name: Domainr
description: Domain name search and availability checking
icon: icon.svg

website: https://domainr.com
privacy_url: https://www.fastly.com/privacy

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: Fastly API Key
  help_url: https://domainr.com/docs/api

instructions: |
  Domainr finds available domain names.
  - Search returns domain suggestions across TLDs
  - Status checks availability of specific domains
  - Status codes: "undelegated" = available, "active" = taken

actions:
  search:
    operation: read
    label: "Search domains"
    rest:
      method: GET
      url: https://api.domainr.com/v2/search
      query:
        query: "{{params.query}}"
        registrar: "dnsimple.com"
      response:
        root: "results"
        mapping:
          domain: ".domain"
          zone: ".zone"
          path: ".path"
          register_url: ".registerURL"

  status:
    operation: read
    label: "Check availability"
    rest:
      method: GET
      url: https://api.domainr.com/v2/status
      query:
        domain: "{{params.domain}}"
      response:
        root: "status"
        mapping:
          domain: ".domain"
          zone: ".zone"
          status: ".status"
          summary: ".summary"
---

# Domainr

Domain name search and availability checking powered by Fastly.

## Setup

1. Get your API key from https://manage.fastly.com/account/personal/tokens
2. Add credential in AgentOS Settings → Providers → Domainr

## Status Codes

- `undelegated` - Available to register
- `active` - Currently registered
- `inactive` - Registered but not resolving
- `marketed` - Listed for sale
- `premium` - Available at premium price
- `unknown` - Status could not be determined

## Usage

Search for domain suggestions:
- Query: "ground" → returns ground.com, ground.io, ground.ai, etc.

Check specific domain availability:
- Domain: "ground.ai" → returns status
