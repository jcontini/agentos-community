---
id: porkbun
name: Porkbun
description: Domain DNS management via Porkbun API
icon: icon.svg

website: https://porkbun.com
privacy_url: https://porkbun.com/products/privacy

auth:
  type: api_key
  label: API Keys (apikey:secretapikey)
  help_url: https://porkbun.com/account/api

instructions: |
  Porkbun DNS management for domains you own.
  
  **Setup:**
  1. Go to https://porkbun.com/account/api
  2. Enable API access
  3. Copy both API Key and Secret API Key
  4. Store as `apikey:secretapikey` (colon-separated)
  
  **Note:** Domain registration not available via API - use web interface.

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  domain:
    terminology: Domain
    mapping:
      fqdn: .domain
      status: .status
      registrar: '"porkbun"'
      expires_at: .expireDate
      auto_renew: '.autoRenew == "yes"'
      created_at: .createDate

  dns_record:
    terminology: DNS Record
    mapping:
      id: .id
      name: .name
      type: .type
      values: '[.content]'
      ttl: '.ttl | tonumber'
      priority: '.prio // null'
      domain: .domain

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  domain.list:
    description: List all domains in your Porkbun account
    returns: domain[]
    rest:
      method: POST
      url: https://api.porkbun.com/api/json/v3/domain/listAll
      body:
        apikey: '.auth.key | split(":") | .[0]'
        secretapikey: '.auth.key | split(":") | .[1]'
      response:
        root: /domains

  domain.get:
    description: Get details for a specific domain
    returns: domain
    params:
      domain: { type: string, required: true, description: "Domain name (e.g. example.com)" }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/domain/getNs/" + .params.domain'
      body:
        apikey: '.auth.key | split(":") | .[0]'
        secretapikey: '.auth.key | split(":") | .[1]'
      response:
        raw: true

  dns_record.list:
    description: List all DNS records for a domain
    returns: dns_record[]
    params:
      domain: { type: string, required: true, description: "Domain name" }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/dns/retrieve/" + .params.domain'
      body:
        apikey: '.auth.key | split(":") | .[0]'
        secretapikey: '.auth.key | split(":") | .[1]'
      response:
        root: /records
        inject:
          domain: .params.domain

  dns_record.create:
    description: Create a new DNS record
    returns: dns_record
    params:
      domain: { type: string, required: true, description: "Domain name" }
      name: { type: string, description: "Subdomain (empty for apex)" }
      type: { type: string, required: true, description: "A, AAAA, CNAME, MX, TXT, NS, SRV" }
      content: { type: string, required: true, description: "Record value" }
      ttl: { type: integer, default: 600, description: "TTL in seconds" }
      prio: { type: integer, description: "Priority (for MX records)" }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/dns/create/" + .params.domain'
      body:
        apikey: '.auth.key | split(":") | .[0]'
        secretapikey: '.auth.key | split(":") | .[1]'
        name: .params.name
        type: .params.type
        content: .params.content
        ttl: '.params.ttl | tostring'
        prio: .params.prio
      response:
        raw: true

  dns_record.update:
    description: Update an existing DNS record
    returns: dns_record
    params:
      domain: { type: string, required: true, description: "Domain name" }
      id: { type: string, required: true, description: "Record ID" }
      name: { type: string, description: "Subdomain" }
      type: { type: string, required: true, description: "Record type" }
      content: { type: string, required: true, description: "Record value" }
      ttl: { type: integer, default: 600, description: "TTL in seconds" }
      prio: { type: integer, description: "Priority" }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/dns/edit/" + .params.domain + "/" + .params.id'
      body:
        apikey: '.auth.key | split(":") | .[0]'
        secretapikey: '.auth.key | split(":") | .[1]'
        name: .params.name
        type: .params.type
        content: .params.content
        ttl: '.params.ttl | tostring'
        prio: .params.prio
      response:
        raw: true

  dns_record.delete:
    description: Delete a DNS record
    returns: dns_record
    params:
      domain: { type: string, required: true, description: "Domain name" }
      id: { type: string, required: true, description: "Record ID" }
    rest:
      method: POST
      url: '"https://api.porkbun.com/api/json/v3/dns/delete/" + .params.domain + "/" + .params.id'
      body:
        apikey: '.auth.key | split(":") | .[0]'
        secretapikey: '.auth.key | split(":") | .[1]'
      response:
        raw: true
---

# Porkbun

DNS management for domains registered with Porkbun.

## Setup

1. Go to https://porkbun.com/account/api
2. Enable API access for your account
3. Copy both the **API Key** and **Secret API Key**
4. Add credentials in AgentOS Settings → Providers → Porkbun

## Capabilities

- List all domains in your account
- View/create/update/delete DNS records
- Supports A, AAAA, CNAME, MX, TXT, NS, SRV records

## Limitations

- **Domain registration NOT available via API** (Porkbun policy)
- Use the web interface to register new domains
- API is for DNS management of existing domains only

## Examples

```bash
# List all your domains
curl -X POST http://localhost:3456/api/plugins/porkbun/domain.list \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor"

# List DNS records for a domain
curl -X POST http://localhost:3456/api/plugins/porkbun/dns_record.list \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "example.com"}'

# Add A record for GitHub Pages
curl -X POST http://localhost:3456/api/plugins/porkbun/dns_record.create \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "example.com", "name": "", "type": "A", "content": "185.199.108.153"}'
```
