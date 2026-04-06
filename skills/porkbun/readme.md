---
id: porkbun
name: Porkbun
description: Domain and DNS management via the Porkbun API
color: "#D62F53"
website: "https://porkbun.com"
privacy_url: "https://porkbun.com/products/privacy"

connections:
  api:
    base_url: https://api.porkbun.com/api/json/v3
    auth:
      type: api_key
      body:
        apikey: .auth.key | split(":") | .[0]
        secretapikey: .auth.key | split(":") | .[1]
    label: API key and secret
    help_url: https://porkbun.com/account/api
---

# Porkbun

Manage domains and DNS records in a Porkbun account.

## Setup

1. Open [Porkbun API Access](https://porkbun.com/account/api)
2. Enable API access for your account
3. Copy both the API key and secret API key
4. Store them in AgentOS as a single credential in the format `apikey:secretapikey`

## What It Covers

- List domains in your Porkbun account
- List DNS records for a domain
- Create, update, and delete DNS records

## Limitations

- Porkbun does not support domain registration through this API
- This skill is for managing existing domains and DNS only

## Example Calls

```js
run({ skill: "porkbun", tool: "list_domains" })

run({
  skill: "porkbun",
  tool: "list_dns_records",
  params: { domain: "example.com" }
})

run({
  skill: "porkbun",
  tool: "create_dns_record",
  params: {
    domain: "example.com",
    name: "",
    type: "A",
    content: "185.199.108.153",
    ttl: 600
  },
  execute: true
})
```
