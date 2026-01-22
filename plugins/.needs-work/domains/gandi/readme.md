---
id: gandi
name: Gandi
description: Domain registration, DNS management, and SSL certificates
icon: icon.svg
color: "#000000"
tags: [domain, dns, ssl, hosting]

website: https://www.gandi.net
privacy_url: https://www.gandi.net/en/contracts/privacy-policy

auth:
  type: api_key
  header: Authorization
  prefix: "Bearer "
  label: Personal Access Token
  help_url: https://admin.gandi.net/organizations/account/pat

instructions: |
  Gandi provides domain registration, DNS, and SSL certificate management.
  
  **Capabilities:**
  - List and manage owned domains
  - Full DNS record management (A, AAAA, CNAME, MX, TXT, etc.)
  - Check domain availability
  - Register new domains
  
  **Common workflows:**
  1. Point domain to GitHub Pages: Add A records for 185.199.108-111.153
  2. Add email: Create MX records
  3. Verify domain: Add TXT record
  
  **Note:** Domain registration requires sufficient account balance.

actions:
  # Domain management
  domain_list:
    operation: read
    label: "List domains"
    description: List all domains in your Gandi account
    rest:
      method: GET
      url: https://api.gandi.net/v5/domain/domains
    response:
      root: "."
      mapping:
        fqdn: ".fqdn"
        status: ".status"
        expires: ".dates.registry_ends_at"
        autorenew: ".autorenew"
        nameserver: ".nameserver.current"

  domain_info:
    operation: read
    label: "Get domain info"
    description: Get detailed information about a specific domain
    rest:
      method: GET
      url: "https://api.gandi.net/v5/domain/domains/{{params.domain}}"
    response:
      raw: true

  domain_check:
    operation: read
    label: "Check availability"
    description: Check if a domain is available for registration
    rest:
      method: GET
      url: https://api.gandi.net/v5/domain/check
      query:
        name: "{{params.domain}}"
    response:
      raw: true

  # DNS management
  dns_list:
    operation: read
    label: "List DNS records"
    description: List all DNS records for a domain
    rest:
      method: GET
      url: "https://api.gandi.net/v5/livedns/domains/{{params.domain}}/records"
    response:
      root: "."
      mapping:
        name: ".rrset_name"
        type: ".rrset_type"
        ttl: ".rrset_ttl"
        values: ".rrset_values"

  dns_get:
    operation: read
    label: "Get DNS record"
    description: Get a specific DNS record by name and type
    rest:
      method: GET
      url: "https://api.gandi.net/v5/livedns/domains/{{params.domain}}/records/{{params.name}}/{{params.type}}"
    response:
      raw: true

  dns_create:
    operation: create
    label: "Create DNS record"
    description: Create a new DNS record (or update if exists)
    rest:
      method: PUT
      url: "https://api.gandi.net/v5/livedns/domains/{{params.domain}}/records/{{params.name}}/{{params.type}}"
      body:
        rrset_ttl: "{{params.ttl | default: 3600}}"
        rrset_values: "{{params.values}}"
    response:
      raw: true

  dns_delete:
    operation: delete
    label: "Delete DNS record"
    description: Delete a DNS record by name and type
    rest:
      method: DELETE
      url: "https://api.gandi.net/v5/livedns/domains/{{params.domain}}/records/{{params.name}}/{{params.type}}"
    response:
      raw: true

  # Bulk DNS operations
  dns_replace_all:
    operation: update
    label: "Replace all DNS records"
    description: Replace all DNS records for a domain (use with caution)
    rest:
      method: PUT
      url: "https://api.gandi.net/v5/livedns/domains/{{params.domain}}/records"
      body:
        items: "{{params.records}}"
    response:
      raw: true

  # SSL Certificates
  ssl_list:
    operation: read
    label: "List SSL certificates"
    description: List all SSL certificates in your account
    rest:
      method: GET
      url: https://api.gandi.net/v5/certificate/issued-certs
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
   - `Certificate` - for SSL (optional)
3. Add the token in AgentOS Settings → Providers → Gandi

## Common Workflows

### Point domain to GitHub Pages

```
# Add A records for apex domain
gandi.dns_create domain="example.com" name="@" type="A" values=["185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"]

# Add CNAME for www
gandi.dns_create domain="example.com" name="www" type="CNAME" values=["username.github.io."]
```

### Add email (Google Workspace)

```
gandi.dns_create domain="example.com" name="@" type="MX" values=["1 aspmx.l.google.com.", "5 alt1.aspmx.l.google.com."]
```

### Verify domain ownership

```
gandi.dns_create domain="example.com" name="@" type="TXT" values=["google-site-verification=abc123"]
```

## DNS Record Types

| Type | Purpose | Example values |
|------|---------|----------------|
| A | IPv4 address | `["185.199.108.153"]` |
| AAAA | IPv6 address | `["2606:50c0:8000::153"]` |
| CNAME | Alias | `["target.example.com."]` (note trailing dot) |
| MX | Mail server | `["10 mail.example.com."]` |
| TXT | Text/verification | `["v=spf1 include:_spf.google.com ~all"]` |
| NS | Nameserver | `["ns1.example.com."]` |

## Notes

- TTL is in seconds (default: 3600 = 1 hour)
- CNAME and MX values need trailing dots for FQDNs
- The `@` symbol represents the apex/root domain
- DNS changes typically propagate within minutes with Gandi's LiveDNS
