---
id: gandi
name: Gandi
description: Domain registration, DNS management, and SSL certificates
icon: icon.png

website: https://www.gandi.net
privacy_url: https://www.gandi.net/en/contracts/privacy-policy

auth:
  header: { Authorization: "Bearer {token}" }
  label: Personal Access Token
  help_url: https://admin.gandi.net/organizations/account/pat

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  domain:
    mapping:
      fqdn: .fqdn
      status: .status
      registrar: '"gandi"'
      expires_at: .dates.registry_ends_at
      auto_renew: .autorenew
      nameservers: .nameserver.current

  dns_record:
    mapping:
      name: .rrset_name
      type: .rrset_type
      ttl: .rrset_ttl
      values: .rrset_values

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  # Domain management
  list_domains:
    description: List all domains in your Gandi account
    returns: domain[]
    rest:
      method: GET
      url: https://api.gandi.net/v5/domain/domains
      response:
        raw: true

  get_domain:
    description: Get detailed information about a specific domain
    returns: domain
    params:
      domain: { type: string, required: true, description: "Domain name (e.g. example.com)" }
    rest:
      method: GET
      url: '"https://api.gandi.net/v5/domain/domains/" + .params.domain'
      response:
        raw: true

  check_domain:
    description: Check if a domain is available for registration
    returns: void
    params:
      domain: { type: string, required: true, description: "Domain to check (e.g. example.com)" }
    rest:
      method: GET
      url: https://api.gandi.net/v5/domain/check
      query:
        name: .params.domain
      response:
        raw: true

  # Utilities - entity-level operations that return dns_record model
  # Named domain.dns_* because they're utilities OF the domain entity

  dns_list_domain:
    description: List all DNS records for a domain
    returns: dns_record[]
    params:
      domain: { type: string, required: true, description: "Domain name" }
    rest:
      method: GET
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records"'
      response:
        raw: true

  dns_get_domain:
    description: Get a specific DNS record by name and type
    returns: dns_record
    params:
      domain: { type: string, required: true, description: "Domain name" }
      name: { type: string, required: true, description: "Record name (@ for apex)" }
      type: { type: string, required: true, description: "Record type (A, CNAME, MX, TXT, etc.)" }
    rest:
      method: GET
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records/" + .params.name + "/" + .params.type'
      response:
        raw: true

  dns_create_domain:
    description: Create or update a DNS record
    returns: dns_record
    params:
      domain: { type: string, required: true, description: "Domain name" }
      name: { type: string, required: true, description: "Record name (@ for apex)" }
      type: { type: string, required: true, description: "Record type (A, CNAME, MX, TXT, etc.)" }
      values: { type: array, required: true, description: "Array of record values" }
      ttl: { type: integer, default: 3600, description: "TTL in seconds" }
    rest:
      method: PUT
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records/" + .params.name + "/" + .params.type'
      body:
        rrset_ttl: '.params.ttl // 3600'
        rrset_values: .params.values
      response:
        raw: true

  dns_delete_domain:
    description: Delete a DNS record by name and type
    returns: void
    params:
      domain: { type: string, required: true, description: "Domain name" }
      name: { type: string, required: true, description: "Record name (@ for apex)" }
      type: { type: string, required: true, description: "Record type" }
    rest:
      method: DELETE
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records/" + .params.name + "/" + .params.type'
      response:
        raw: true
---

# Gandi

Domain registration and DNS management via Gandi's API.

## Setup

1. Go to https://admin.gandi.net/organizations/account/pat
2. Create a Personal Access Token with appropriate permissions:
   - `Domain` - for domain management
   - `LiveDNS` - for DNS records
3. Add the token in AgentOS Settings → Providers → Gandi

## Common Workflows

### Point domain to GitHub Pages

```bash
# Add A records for apex domain
curl -X POST http://localhost:3456/api/adapters/gandi/domain.dns_create \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "example.com", "name": "@", "type": "A", "values": ["185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"]}'

# Add CNAME for www
curl -X POST http://localhost:3456/api/adapters/gandi/domain.dns_create \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "example.com", "name": "www", "type": "CNAME", "values": ["username.github.io."]}'
```

### Check domain availability

```bash
curl -X POST http://localhost:3456/api/adapters/gandi/domain.check \
  -H "Content-Type: application/json" \
  -H "X-Agent: cursor" \
  -d '{"domain": "coolname.com"}'
```

## DNS Record Types

| Type | Purpose | Example values |
|------|---------|----------------|
| A | IPv4 address | `["185.199.108.153"]` |
| AAAA | IPv6 address | `["2606:50c0:8000::153"]` |
| CNAME | Alias | `["target.example.com."]` (note trailing dot) |
| MX | Mail server | `["10 mail.example.com."]` |
| TXT | Text/verification | `["v=spf1 include:_spf.google.com ~all"]` |

## Notes

- TTL is in seconds (default: 3600 = 1 hour)
- CNAME and MX values need trailing dots for FQDNs
- The `@` symbol represents the apex/root domain
- DNS changes typically propagate within minutes with Gandi's LiveDNS
