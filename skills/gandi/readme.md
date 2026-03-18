---
id: gandi
name: Gandi
description: Domain and DNS management via the Gandi API
icon: icon.svg
color: "#E74B3C"

website: https://www.gandi.net
privacy_url: https://www.gandi.net/en/contracts/privacy-policy

connections:
  api:
    base_url: "https://api.gandi.net/v5"
    header:
      Authorization: '"Bearer " + .auth.key'
    label: Personal Access Token
    help_url: https://admin.gandi.net/organizations/account/pat

adapters:
  domain:
    id: .fqdn
    name: .fqdn
    url: '"https://" + .fqdn'
    data.status: .status
    data.registrar: '"gandi"'
    data.expires_at: .dates.registry_ends_at
    data.auto_renew: .autorenew
    data.nameservers: .nameserver.current

  dns_record:
    id: '.domain + ":" + .rrset_name + ":" + .rrset_type'
    name: 'if (.rrset_name // "") == "" or .rrset_name == "@" then .domain else .rrset_name + "." + .domain end'
    text: '.rrset_type + " " + ((.rrset_values // []) | join(", "))'
    data.domain: .domain
    data.name: .rrset_name
    data.type: .rrset_type
    data.ttl: .rrset_ttl
    data.values: .rrset_values

operations:
  list_domains:
    description: List all domains in your Gandi account
    returns: domain[]
    rest:
      method: GET
      url: /domain/domains
      response:
        raw: true

  get_domain:
    description: Get details for a single domain
    returns: domain
    params:
      domain:
        type: string
        required: true
        description: Domain name, for example example.com
    rest:
      method: GET
      url: '"https://api.gandi.net/v5/domain/domains/" + .params.domain'
      response:
        raw: true

  list_dns_records:
    description: List DNS records for a domain
    returns: dns_record[]
    params:
      domain:
        type: string
        required: true
        description: Domain name
    rest:
      method: GET
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records"'
      response:
        raw: true
        inject:
          domain: .params.domain

  get_dns_record:
    description: Get one DNS record by name and type
    returns: dns_record
    params:
      domain:
        type: string
        required: true
        description: Domain name
      name:
        type: string
        required: true
        description: Record name, use @ for the apex
      type:
        type: string
        required: true
        description: Record type such as A, AAAA, CNAME, MX, or TXT
    rest:
      method: GET
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records/" + .params.name + "/" + .params.type'
      response:
        raw: true
        inject:
          domain: .params.domain

  upsert_dns_record:
    description: Create or replace a DNS record
    returns: void
    params:
      domain:
        type: string
        required: true
        description: Domain name
      name:
        type: string
        required: true
        description: Record name, use @ for the apex
      type:
        type: string
        required: true
        description: Record type such as A, AAAA, CNAME, MX, or TXT
      values:
        type: array
        required: true
        description: Array of record values
      ttl:
        type: integer
        default: 3600
        description: TTL in seconds
    rest:
      method: PUT
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records/" + .params.name + "/" + .params.type'
      body:
        rrset_ttl: '(.params.ttl // 3600)'
        rrset_values: .params.values
      response:
        raw: true

  delete_dns_record:
    description: Delete a DNS record
    returns: void
    params:
      domain:
        type: string
        required: true
        description: Domain name
      name:
        type: string
        required: true
        description: Record name, use @ for the apex
      type:
        type: string
        required: true
        description: Record type
    rest:
      method: DELETE
      url: '"https://api.gandi.net/v5/livedns/domains/" + .params.domain + "/records/" + .params.name + "/" + .params.type'
      response:
        raw: true
---

# Gandi

Manage domains and DNS records in a Gandi account.

## Setup

1. Open [Gandi Personal Access Tokens](https://admin.gandi.net/organizations/account/pat)
2. Create a token with `Domain` and `LiveDNS` permissions
3. Store that token in AgentOS as the Gandi credential

## What It Covers

- List domains in your Gandi account
- Inspect one domain in detail
- List DNS records for a domain
- Create, replace, and delete DNS records

## Example Calls

```js
run({ skill: "gandi", tool: "list_domains" })

run({
  skill: "gandi",
  tool: "list_dns_records",
  params: { domain: "example.com" }
})

run({
  skill: "gandi",
  tool: "upsert_dns_record",
  params: {
    domain: "example.com",
    name: "@",
    type: "A",
    values: ["185.199.108.153", "185.199.109.153"],
    ttl: 3600
  }
})

run({
  skill: "gandi",
  tool: "delete_dns_record",
  params: {
    domain: "example.com",
    name: "www",
    type: "CNAME"
  }
})
```

## Notes

- Use `@` for the apex record name
- `upsert_dns_record` replaces the full record set for that name and type
- CNAME and MX values usually need fully qualified targets
