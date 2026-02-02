---
depends_on: []
inspired_by: []
---

# Lob Connector Spec

Example of a "mail" capability provider that other plugins can use.

---

## Overview

Lob is a physical mail API. This plugin:
- **Provides:** `mail`, `physical-mail`, `letters`, `postcards`, `checks`
- **Enables:** Other plugins (like `tx-dot`) to mail documents without knowing Lob's specifics
- **Handles:** Letters, postcards, checks, address verification

---

## The Connector

```yaml
# apps/lob/readme.md
---
id: lob
name: Lob
description: Send physical mail programmatically — letters, postcards, and checks
icon: icon.png

website: https://lob.com
docs_url: https://docs.lob.com

# What capabilities this plugin provides
provides: [mail, physical-mail, letters, postcards, checks, address-verification]


auth:
  type: api_key
  header: Authorization
  auth_type: Basic  # Lob uses Basic auth with API key as username
  label: Lob API Key
  help_url: https://dashboard.lob.com/settings/api-keys

instructions: |
  Lob sends physical mail via USPS. Use this plugin to:
  - Mail letters and documents
  - Send postcards
  - Print and mail checks
  - Verify addresses
  
  **Pricing:**
  - Letters (First Class): ~$0.63 + $0.06/page
  - Postcards (4x6): ~$0.40
  - Checks: ~$1.50
  
  **Delivery times:**
  - First Class: 3-5 business days
  - Standard: 5-10 business days

actions:
  # ============================================================
  # SEND LETTER
  # ============================================================
  send_letter:
    description: |
      Mail a letter with an attached PDF document.
      Lob prints and mails it via USPS.
    readonly: false
    params:
      # Recipient
      to_name: Recipient name // "Dallas County Tax Office"
      to_address_line1: Street address // "1201 Elm St"
      to_address_line2?: Unit/Suite // "Suite 2600"
      to_city: City // "Dallas"
      to_state: State code // "TX"
      to_zip: ZIP code // "75270"
      
      # Sender
      from_name: Sender name // "Joe Smith"
      from_address_line1: Street address // "456 Oak Ave"
      from_address_line2?: Unit/Apt // "Apt 2B"
      from_city: City // "Dallas"
      from_state: State code // "TX"
      from_zip: ZIP code // "75201"
      
      # Document
      file: PDF file path or URL // "/tmp/form.pdf" or "https://example.com/doc.pdf"
      
      # Options
      mail_type?: USPS mail class // "usps_first_class" | "usps_standard"
      color?: Print in color // false
      double_sided?: Print both sides // false
      address_placement?: Where to print address // "top_first_page" | "insert_blank_page"
      return_envelope?: Include return envelope // false
      
      # Metadata
      description?: Internal description // "VTR-146 for Joe Smith"
      metadata?: Custom key-value pairs // {"form_type": "VTR-146", "vehicle": "ABC1234"}
    
    rest:
      method: POST
      url: https://api.lob.com/v1/letters
      body:
        to:
          name: "{{params.to_name}}"
          address_line1: "{{params.to_address_line1}}"
          address_line2: "{{params.to_address_line2}}"
          address_city: "{{params.to_city}}"
          address_state: "{{params.to_state}}"
          address_zip: "{{params.to_zip}}"
        from:
          name: "{{params.from_name}}"
          address_line1: "{{params.from_address_line1}}"
          address_line2: "{{params.from_address_line2}}"
          address_city: "{{params.from_city}}"
          address_state: "{{params.from_state}}"
          address_zip: "{{params.from_zip}}"
        file: "{{params.file}}"
        color: "{{params.color | default: false}}"
        double_sided: "{{params.double_sided | default: false}}"
        address_placement: "{{params.address_placement | default: 'top_first_page'}}"
        return_envelope: "{{params.return_envelope | default: false}}"
        mail_type: "{{params.mail_type | default: 'usps_first_class'}}"
        description: "{{params.description}}"
        metadata: "{{params.metadata}}"
      response:
        mapping:
          id: ".id"
          status: ".send_date | if . then 'scheduled' else 'processing'"
          tracking_id: ".id"
          tracking_url: ".url"
          expected_delivery: ".expected_delivery_date"
          carrier: ".carrier"
          cost: ".price"
          pages: ".pages"

  # ============================================================
  # SEND POSTCARD
  # ============================================================
  send_postcard:
    description: Send a postcard with front and back designs
    readonly: false
    params:
      to_name: Recipient name // "John Doe"
      to_address_line1: Street address // "123 Main St"
      to_city: City // "Austin"
      to_state: State // "TX"
      to_zip: ZIP // "78701"
      
      from_name?: Sender name // "Joe Smith"
      from_address_line1?: Street // "456 Oak Ave"
      from_city?: City // "Dallas"
      from_state?: State // "TX"
      from_zip?: ZIP // "75201"
      
      front: Front image/PDF URL or path // "https://example.com/front.png"
      back?: Back image/PDF (or use message) // "https://example.com/back.png"
      message?: Text message for back // "Thank you for your business!"
      
      size?: Postcard size // "4x6" | "6x9" | "6x11"
      mail_type?: Mail class // "usps_first_class" | "usps_standard"
    
    rest:
      method: POST
      url: https://api.lob.com/v1/postcards
      body:
        to:
          name: "{{params.to_name}}"
          address_line1: "{{params.to_address_line1}}"
          address_city: "{{params.to_city}}"
          address_state: "{{params.to_state}}"
          address_zip: "{{params.to_zip}}"
        from:
          name: "{{params.from_name}}"
          address_line1: "{{params.from_address_line1}}"
          address_city: "{{params.from_city}}"
          address_state: "{{params.from_state}}"
          address_zip: "{{params.from_zip}}"
        front: "{{params.front}}"
        back: "{{params.back | default: params.message}}"
        size: "{{params.size | default: '4x6'}}"
        mail_type: "{{params.mail_type | default: 'usps_first_class'}}"
      response:
        mapping:
          id: ".id"
          status: "'scheduled'"
          expected_delivery: ".expected_delivery_date"
          cost: ".price"

  # ============================================================
  # VERIFY ADDRESS
  # ============================================================
  verify_address:
    description: |
      Verify and standardize a US address.
      Returns USPS-standardized format and deliverability.
    readonly: true
    params:
      address_line1: Street address // "123 Main Street"
      address_line2?: Unit/Suite // "Apt 2B"
      city: City // "Austin"
      state: State // "TX"
      zip?: ZIP code // "78701"
    
    rest:
      method: POST
      url: https://api.lob.com/v1/us_verifications
      body:
        primary_line: "{{params.address_line1}}"
        secondary_line: "{{params.address_line2}}"
        city: "{{params.city}}"
        state: "{{params.state}}"
        zip_code: "{{params.zip}}"
      response:
        mapping:
          deliverable: ".deliverability | . == 'deliverable'"
          deliverability: ".deliverability"
          address_line1: ".primary_line"
          address_line2: ".secondary_line"
          city: ".components.city"
          state: ".components.state"
          zip: ".components.zip_code"
          zip_plus_4: ".components.zip_code_plus_4"
          county: ".components.county"
          latitude: ".components.latitude"
          longitude: ".components.longitude"
          record_type: ".deliverability_analysis.dpv_footnotes"

  # ============================================================
  # GET LETTER STATUS
  # ============================================================
  get_status:
    description: Check the status and tracking info for a sent letter
    readonly: true
    params:
      id: Letter ID from send_letter // "ltr_abc123def456"
    
    rest:
      method: GET
      url: "https://api.lob.com/v1/letters/{{params.id}}"
      response:
        mapping:
          id: ".id"
          status: ".send_date | if . then 'mailed' else 'processing'"
          send_date: ".send_date"
          expected_delivery: ".expected_delivery_date"
          carrier: ".carrier"
          tracking_number: ".tracking_number"
          tracking_events: ".tracking_events"
          pages: ".pages"
          cost: ".price"

  # ============================================================
  # LIST LETTERS
  # ============================================================
  list_letters:
    description: List previously sent letters
    readonly: true
    params:
      limit?: Max results // 25
      date_created_after?: Filter by date // "2025-01-01"
      date_created_before?: Filter by date // "2025-01-31"
      metadata?: Filter by metadata // {"form_type": "VTR-146"}
    
    rest:
      method: GET
      url: https://api.lob.com/v1/letters
      query:
        limit: "{{params.limit | default: 25}}"
        date_created[gt]: "{{params.date_created_after}}"
        date_created[lt]: "{{params.date_created_before}}"
        metadata: "{{params.metadata | to_json}}"
      response:
        root: "data"
        mapping:
          id: "[].id"
          description: "[].description"
          send_date: "[].send_date"
          expected_delivery: "[].expected_delivery_date"
          to_name: "[].to.name"
          status: "[].send_date | if . then 'mailed' else 'processing'"

  # ============================================================
  # CANCEL LETTER
  # ============================================================
  cancel:
    description: Cancel a letter that hasn't been sent yet
    readonly: false
    params:
      id: Letter ID // "ltr_abc123def456"
    
    rest:
      method: DELETE
      url: "https://api.lob.com/v1/letters/{{params.id}}"
      response:
        mapping:
          id: ".id"
          deleted: ".deleted"
---

# Lob

Send physical mail programmatically — letters, postcards, and checks.

## Capabilities Provided

This plugin **provides** the following capabilities for other plugins/agents:

- `mail` — General physical mail sending
- `physical-mail` — Alias for mail
- `letters` — Letter/document mailing
- `postcards` — Postcard mailing
- `checks` — Check printing and mailing
- `address-verification` — USPS address standardization

## Setup

1. Create account at https://lob.com
2. Get API key from https://dashboard.lob.com/settings/api-keys
3. Add to AgentOS Settings → Apps → Lob

**Test Mode:** Lob provides test API keys that simulate sending without actual mail. Use `test_*` keys for development.

## Pricing

| Item | Cost |
|------|------|
| Letter (First Class) | ~$0.63 + $0.06/page |
| Letter (Standard) | ~$0.53 + $0.05/page |
| Postcard (4x6) | ~$0.40 |
| Postcard (6x9) | ~$0.59 |
| Check | ~$1.50 |
| Address Verification | ~$0.01 |

## Delivery Times

| Mail Type | Delivery |
|-----------|----------|
| First Class | 3-5 business days |
| Standard | 5-10 business days |

## Examples

### Send a Letter

```
Apps(
  app: "lob",
  action: "send_letter",
  params: {
    to_name: "Dallas County Tax Office",
    to_address_line1: "1201 Elm St",
    to_city: "Dallas",
    to_state: "TX",
    to_zip: "75270",
    from_name: "Joe Smith",
    from_address_line1: "456 Oak Ave",
    from_city: "Dallas",
    from_state: "TX",
    from_zip: "75201",
    file: "/tmp/my_form.pdf"
  },
  execute: true
)
```

### Verify an Address

```
Apps(
  app: "lob",
  action: "verify_address",
  params: {
    address_line1: "123 main st",
    city: "austin",
    state: "tx"
  }
)
```

Returns standardized address with deliverability status.

### Check Letter Status

```
Apps(
  app: "lob",
  action: "get_status",
  params: { id: "ltr_abc123def456" }
)
```

## How Other Connectors Use This

The `tx-dot` plugin (or any plugin needing mail) can use Lob without knowing its specifics:

**Option 1: Agent discovers and calls**
```
Agent: "I need to mail this PDF"
Agent: *discovers lob provides 'mail'*
Agent: *calls Apps(app: "lob", action: "readme")*
Agent: *calls Apps(app: "lob", action: "send_letter", ...)*
```

**Option 2: Capability reference (future)**
```yaml
# In tx-dot plugin
steps:
  - id: mail_form
    capability: mail
    action: send_letter  
    # AgentOS resolves "mail" → user's preferred provider (lob)
```

## Address Requirements

Lob validates addresses and may reject undeliverable ones. Use `verify_address` first if unsure:

```
Apps(app: "lob", action: "verify_address", params: {...})
# If deliverable: true → proceed with send_letter
# If deliverable: false → address may be wrong, verify with user
```
```

---

## Alternative Providers

Other plugins could also provide `mail`:

| Connector | Provides | Notes |
|-----------|----------|-------|
| `lob` | mail, letters, postcards, checks | Most popular, good API |
| `postgrid` | mail, letters, checks | Canadian option |
| `click2mail` | mail, letters | Bulk mail focused |
| `sendgrid` | email (not physical) | Different capability |

User sets preference in AgentOS Settings → Capabilities → mail: lob
