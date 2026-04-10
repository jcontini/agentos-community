---
id: gandi
name: Gandi
description: Domain and DNS management via the Gandi API
color: "#E74B3C"
website: "https://www.gandi.net"
privacy_url: "https://www.gandi.net/en/contracts/privacy-policy"

connections:
  api:
    base_url: https://api.gandi.net/v5
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: Personal Access Token
    help_url: https://admin.gandi.net/organizations/account/pat
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
