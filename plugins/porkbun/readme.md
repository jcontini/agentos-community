---
id: porkbun
name: Porkbun
description: Domain DNS management via Porkbun API
icon: icon.svg
color: "#d62f53"
tags: [domain, dns]

website: https://porkbun.com
privacy_url: https://porkbun.com/products/privacy

auth:
  type: api_key
  label: API Keys (apikey:secretapikey)
  help_url: https://porkbun.com/account/api
  # Porkbun uses two keys - store as "apikey:secretapikey"

instructions: |
  Porkbun DNS management. Store credentials as "apikey:secretapikey" (colon-separated).
  
  **Capabilities:**
  - List all domains
  - Get/create/update/delete DNS records
  - Check domain pricing
  
  **Note:** Domain registration not available via API - use web interface.

actions:
  ping:
    operation: read
    label: "Test API connection"
    description: Verify API credentials are working
    rest:
      method: POST
      url: https://api.porkbun.com/api/json/v3/ping
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
    response:
      raw: true

  domain_list:
    operation: read
    label: "List domains"
    description: List all domains in your Porkbun account
    rest:
      method: POST
      url: https://api.porkbun.com/api/json/v3/domain/listAll
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
    response:
      root: ".domains"
      mapping:
        domain: ".domain"
        status: ".status"
        tld: ".tld"
        create_date: ".createDate"
        expire_date: ".expireDate"
        auto_renew: ".autoRenew"

  dns_list:
    operation: read
    label: "List DNS records"
    description: List all DNS records for a domain
    rest:
      method: POST
      url: "https://api.porkbun.com/api/json/v3/dns/retrieve/{{params.domain}}"
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
    response:
      root: ".records"
      mapping:
        id: ".id"
        name: ".name"
        type: ".type"
        content: ".content"
        ttl: ".ttl"
        prio: ".prio"

  dns_create:
    operation: create
    label: "Create DNS record"
    description: Create a new DNS record
    rest:
      method: POST
      url: "https://api.porkbun.com/api/json/v3/dns/create/{{params.domain}}"
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
        name: "{{params.name}}"
        type: "{{params.type}}"
        content: "{{params.content}}"
        ttl: "{{params.ttl | default: '600'}}"
        prio: "{{params.prio}}"
    response:
      raw: true

  dns_update:
    operation: update
    label: "Update DNS record"
    description: Update an existing DNS record by ID
    rest:
      method: POST
      url: "https://api.porkbun.com/api/json/v3/dns/edit/{{params.domain}}/{{params.id}}"
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
        name: "{{params.name}}"
        type: "{{params.type}}"
        content: "{{params.content}}"
        ttl: "{{params.ttl | default: '600'}}"
        prio: "{{params.prio}}"
    response:
      raw: true

  dns_delete:
    operation: delete
    label: "Delete DNS record"
    description: Delete a DNS record by ID
    rest:
      method: POST
      url: "https://api.porkbun.com/api/json/v3/dns/delete/{{params.domain}}/{{params.id}}"
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
    response:
      raw: true

  dns_delete_by_type:
    operation: delete
    label: "Delete DNS records by type"
    description: Delete all DNS records of a specific type and subdomain
    rest:
      method: POST
      url: "https://api.porkbun.com/api/json/v3/dns/deleteByNameType/{{params.domain}}/{{params.type}}/{{params.subdomain}}"
      body:
        apikey: "{{auth.apikey}}"
        secretapikey: "{{auth.secretapikey}}"
    response:
      raw: true
---

# Porkbun

DNS management for domains registered with Porkbun.

## Setup

1. Go to https://porkbun.com/account/api
2. Enable API access for your account
3. Copy both the API Key and Secret API Key
4. In AgentOS, store as: `apikey:secretapikey` (colon-separated)

## Limitations

- Domain registration is NOT available via API (Porkbun policy)
- Use the web interface to register new domains
- API is for DNS management of existing domains only

## DNS Record Types

| Type | Purpose |
|------|---------|
| A | IPv4 address |
| AAAA | IPv6 address |
| CNAME | Alias to another domain |
| MX | Mail server |
| TXT | Text records (SPF, DKIM, verification) |
| NS | Nameserver |

## Examples

```
# List all domains
porkbun.domain_list

# List DNS records
porkbun.dns_list domain="example.com"

# Add A record for GitHub Pages
porkbun.dns_create domain="example.com" name="" type="A" content="185.199.108.153"

# Add www CNAME
porkbun.dns_create domain="example.com" name="www" type="CNAME" content="username.github.io"
```
