---
depends_on: []
inspired_by:
  - user-profile
---

# TX-DOT Connector Spec

Example of what a government services plugin could look like with infinite resources.

---

## Overview

A plugin for Texas Department of Motor Vehicles (TxDMV) that can:
- Fill government PDF forms with user data
- Validate filled forms using vision AI
- Add signatures (scanned image or autopen service)
- Mail physical documents to county offices
- Track submission status

This represents the "dream" architecture for government form automation.

---

## The Connector

```yaml
# apps/tx-dot/readme.md
---
id: tx-dot
name: Texas DMV
description: Submit Texas vehicle registration forms, address changes, and more
icon: icon.png

website: https://www.txdmv.gov
tags: [government, dmv, vehicle, registration, texas, forms]

# This plugin doesn't "provide" capabilities - it consumes them
# (It's not a utility other plugins would use)

# What capabilities this plugin needs from other plugins
requires:
  pdf-forms: Fill forms, stamp signature  # pdf-lib (built-in), pdftk, qpdf, adobe-api
  mail: Send physical forms               # lob, postgrid, click2mail
  vision: Validate filled forms           # claude, gpt-4v, gemini

# No direct auth - uses capabilities from other plugins
# (mail provider has its own auth, vision provider has its own auth)

# User profile fields this plugin uses (see user-profile.md spec)
profile:
  required:
    - identity.legal_name.full        # Owner name on forms
    - addresses.residence             # Current address (with county!)
    - documents.signature.image_path  # For signing forms
  optional:
    - addresses.previous              # Previous address for change forms
    - contact.phone.mobile            # Contact number
    - vehicles                        # Auto-fill vehicle info (VIN, plate, etc.)

instructions: |
  This plugin automates Texas DMV form submissions.
  
  **Important:** Forms are physically mailed. Allow 5-10 business days for processing.
  
  **Signature options:**
  - `signature_type: "image"` — Uses your stored signature image (fastest)
  - `signature_type: "autopen"` — Uses autopen service for wet ink (most accepted)
  - `signature_type: "none"` — Generates unsigned PDF for you to sign manually
  
  **Validation:** Each form is checked by vision AI before mailing to catch:
  - Truncated text
  - Misaligned fields
  - Wrong date formats
  - Missing required fields
  
  **Workflow:**
  1. Call the action (e.g., `update_address`)
  2. Connector fills form + validates with AI
  3. If validation fails, auto-retries with adjustments (up to 3x)
  4. Adds signature
  5. **Opens PDF for your review** (you confirm before mailing)
  6. Mails to county office
  5. Validates signature placement
  6. Mails to correct county office
  7. Returns tracking info

actions:
  # ============================================================
  # ADDRESS CHANGE (VTR-146)
  # ============================================================
  update_address:
    description: |
      Change the address on your Texas vehicle registration.
      Fills VTR-146 form, validates, signs, and mails to county office.
    readonly: false
    params:
      # Vehicle info (resolved from profile if omitted - will ask if ambiguous)
      vin?: VIN // "1HGCM82633A123456"
      plate?: Plate // "ABC1234"
      year?: Year // 2020
      make?: Make // "Honda"
      model?: Model // "Accord"
      vehicle_label?: Select vehicle by label // "Model 3" | "F-150"
      
      # Address info (uses profile if not provided)
      old_address?: Previous address (uses profile.addresses.residence if omitted)
      new_address: New address (or set profile.addresses.residence first)
      
      # Options
      signature_type?: How to sign // "image" | "autopen" | "none"
      county?: County for mailing (auto-detected from new_address if omitted) // "Dallas"
      
      # Advanced
      font_size?: Override font size // 10
      validate_model?: Vision model for validation // "claude" | "gpt" | "gemini"
      skip_validation?: Skip AI validation (not recommended) // false
      skip_review?: Skip human review before mailing (not recommended) // false
    
    returns:
      status: "mailed" | "validation_failed" | "ready_for_signature"
      tracking_id?: Lob tracking ID
      pdf_path: Path to generated PDF
      validation_results?: Vision AI validation details
      estimated_delivery?: Date range
      county_office: Where it was mailed
    
    # Multi-step execution with retry logic
    steps:
      # Step 0: Resolve vehicle from profile (if not provided in params)
      # IMPORTANT: Never silently pick from array — require explicit selection
      - id: resolve_vehicle
        resolve:
          source: profile.vehicles
          select_by:
            - params.vin                    # 1. Explicit VIN in params
            - params.vehicle_label          # 2. Explicit label in params
            - count: 1                      # 3. Only one item exists (unambiguous)
          on_ambiguous:                     # Multiple items, no explicit selection
            error: "Multiple vehicles found. Please specify which vehicle."
            prompt:                         # Return options for user/agent to choose
              field: "vehicle_label"
              options: "{{profile.vehicles | map: 'label'}}"
              details: "{{profile.vehicles | map: '{label} - {year} {make} {model} ({plate.number})'}}"
      
      # Step 1: Download blank form
      - id: download_form
        http:
          method: GET
          url: https://www.txdmv.gov/sites/default/files/form_files/VTR_146.pdf
          save_to: "{{temp_dir}}/vtr146_blank.pdf"
      
      # Step 2: Fill the PDF form using form definition
      - id: fill_form
        capability: pdf-forms           # Routes to user's provider (pdf-lib, pdftk, etc.)
        action: fill
        params:
          input: "{{download_form.path}}"
          output: "{{temp_dir}}/vtr146_filled_{{uuid}}.pdf"
          form_def: "forms/vtr_146.yaml"
          
          data:
            owner.first: "{{profile.identity.legal_name.first}}"
            owner.last: "{{profile.identity.legal_name.last}}"
            old_address.line1: "{{params.old_address.line1 | default: profile.addresses.residence.lines[0]}}"
            old_address.city: "{{params.old_address.city | default: profile.addresses.residence.city}}"
            old_address.state: "TX"
            old_address.zip: "{{params.old_address.zip | default: profile.addresses.residence.postal_code}}"
            old_address.county: "{{params.old_address.county | default: profile.addresses.residence.county}}"
            new_address.line1: "{{params.new_address.line1 | default: profile.addresses.residence.lines[0]}}"
            new_address.city: "{{params.new_address.city | default: profile.addresses.residence.city}}"
            new_address.state: "TX"
            new_address.zip: "{{params.new_address.zip | default: profile.addresses.residence.postal_code}}"
            vehicle.vin: "{{params.vin | default: resolve_vehicle.vehicle.vin}}"
            vehicle.plate: "{{params.plate | default: resolve_vehicle.vehicle.plate.number}}"
            vehicle.year: "{{params.year | default: resolve_vehicle.vehicle.year}}"
            vehicle.make: "{{params.make | default: resolve_vehicle.vehicle.make}}"
            date: "{{now | date: 'MM/DD/YYYY'}}"
          
          options:
            validate: true
            flatten: false
      
      # Step 3: Convert to image for validation
      - id: render_preview
        capability: pdf-forms
        action: render
        params:
          input: "{{fill_form.output}}"
          output: "{{temp_dir}}/vtr146_preview_{{uuid}}.png"
          dpi: 150
          page: 1
      
      # Step 4: Vision AI validation
      - id: validate_form
        skip_if: "{{params.skip_validation}}"
        vision:
          model: "{{params.validate_model | default: 'claude'}}"
          image: "{{render_preview.output}}"
          prompt: |
            You are validating a filled Texas DMV form (VTR-146 - Change of Address).
            
            Check EVERY filled field for these issues:
            1. **Truncation:** Text cut off at box edges
            2. **Overflow:** Text extending outside box boundaries
            3. **Font size:** Too small to read OR too large for box
            4. **Date format:** Must be MM/DD/YYYY
            5. **Alignment:** Text should be left-aligned, readable
            6. **Missing fields:** Any required fields left empty
            7. **Legibility:** Can all text be clearly read?
            
            The form should have these fields filled:
            - Owner name
            - Current/old address (street, city, state, zip)
            - New address (street, city, state, zip)
            - Vehicle VIN
            - License plate number
            - Date
            
            Return JSON only:
            {
              "passed": true/false,
              "confidence": 0.0-1.0,
              "issues": [
                {"field": "field_name", "issue": "description", "severity": "error|warning"}
              ],
              "suggestions": {
                "font_size": suggested_size_if_needed,
                "truncated_fields": ["field names that need shorter text"]
              }
            }
          response:
            parse: json
        
        # Retry logic if validation fails
        on_failure:
          max_retries: 3
          retry_with:
            # Adjust font size based on suggestions
            font_size: "{{validate_form.suggestions.font_size | default: params.font_size - 1}}"
          goto: fill_form
      
      # Step 5: Add signature (uses "signature" capability)
      - id: add_signature
        skip_if: "{{params.signature_type == 'none'}}"
        capability: signature  # ← Resolved to user's preferred provider (autopen, image-stamp, etc.)
        action: sign
        params:
          document: "{{fill_form.output}}"
          signature_source: "{{profile.documents.signature.image_path}}"
          output: "{{temp_dir}}/vtr146_signed_{{uuid}}.pdf"
          position:
            page: 1
            x: 400
            y: 650
            width: 150
            height: 50
          # Provider handles the method (autopen vs image stamp vs e-sign)
      
      # Step 6: Validate signature placement
      - id: validate_signature
        skip_if: "{{params.signature_type == 'none' or params.skip_validation}}"
        vision:
          model: "{{params.validate_model | default: 'claude'}}"
          image_from_pdf:
            path: "{{add_signature.output}}"
            page: 1
            dpi: 150
          prompt: |
            Check the signature on this Texas DMV form:
            
            1. Is there a visible signature in the signature field?
            2. Is the signature the right size (not too small, not overflowing)?
            3. Is it positioned correctly in the signature box?
            4. Is it legible (looks like a real signature)?
            
            Return JSON:
            {
              "passed": true/false,
              "issues": ["list of problems"],
              "suggestions": {"width": num, "height": num, "x_offset": num, "y_offset": num}
            }
        
        on_failure:
          max_retries: 2
          retry_with:
            # Adjust signature position/size
            position:
              x: "{{validate_signature.suggestions.x_offset + 400}}"
              y: "{{validate_signature.suggestions.y_offset + 650}}"
              width: "{{validate_signature.suggestions.width | default: 150}}"
              height: "{{validate_signature.suggestions.height | default: 50}}"
          goto: add_signature
      
      # Step 7: Determine county office address
      - id: lookup_county
        sql:
          database: "{{agentos_data_dir}}/reference/texas_counties.db"
          query: |
            SELECT 
              county_name,
              tax_office_name,
              tax_office_address,
              tax_office_city,
              tax_office_zip
            FROM county_tax_offices
            WHERE county_name = '{{params.county | default: (params.new_address | county_from_zip)}}'
            LIMIT 1
      
      # Step 8: User reviews before mailing
      - id: user_review
        skip_if: "{{params.skip_review}}"
        ask:
          type: review
          title: "Review before mailing"
          message: |
            Please review your filled VTR-146 form before it's mailed to:
            {{lookup_county.tax_office_name}}
            {{lookup_county.tax_office_address}}
            {{lookup_county.tax_office_city}}, TX {{lookup_county.tax_office_zip}}
          
          # Opens the PDF in the default app (Preview on macOS)
          file: "{{add_signature.output | default: fill_form.output}}"
          
          actions:
            - id: approve
              label: "Looks good — mail it"
            - id: cancel
              label: "Cancel"
      
      # Step 9: Mail the form (uses "mail" capability - resolved to user's preferred provider)
      - id: mail_form
        skip_if: "{{params.signature_type == 'none' or user_review.response == 'cancel'}}"
        capability: mail  # ← AgentOS resolves to user's preferred mail provider (lob, postgrid, etc.)
        action: send_letter
        params:
          # From (sender)
          from_name: "{{profile.identity.legal_name.full}}"
          from_address_line1: "{{params.new_address | address_line1}}"
          from_city: "{{params.new_address | city}}"
          from_state: "TX"
          from_zip: "{{params.new_address | zip}}"
          # To (county office)
          to_name: "{{lookup_county.tax_office_name}}"
          to_address_line1: "{{lookup_county.tax_office_address}}"
          to_city: "{{lookup_county.tax_office_city}}"
          to_state: "TX"
          to_zip: "{{lookup_county.tax_office_zip}}"
          # Document
          file: "{{add_signature.output | default: fill_form.output}}"
          # Options (provider adapts these to its own format)
          mail_type: "usps_first_class"
          double_sided: false
      
      # Step 10: Log the submission
      - id: log_submission
        sql:
          database: "{{agentos_data_dir}}/agentos.db"
          query: |
            INSERT INTO form_submissions (
              form_type, status, tracking_id, submitted_at,
              county, vehicle_vin, pdf_path
            ) VALUES (
              'VTR-146', 
              '{{mail_form.status | default: "ready_for_signature"}}',
              '{{mail_form.tracking_id}}',
              datetime('now'),
              '{{lookup_county.county_name}}',
              '{{params.vin}}',
              '{{add_signature.output | default: fill_form.output}}'
            )
    
    response:
      mapping:
        status: "{{mail_form.status | default: 'ready_for_signature'}}"
        tracking_id: "{{mail_form.tracking_id}}"
        pdf_path: "{{add_signature.output | default: fill_form.output}}"
        validation_results:
          form: "{{validate_form}}"
          signature: "{{validate_signature}}"
        estimated_delivery: "{{mail_form.expected_delivery}}"
        county_office: 
          name: "{{lookup_county.tax_office_name}}"
          address: "{{lookup_county.tax_office_address}}, {{lookup_county.tax_office_city}}, TX {{lookup_county.tax_office_zip}}"

  # ============================================================
  # VEHICLE TRANSFER NOTIFICATION
  # ============================================================
  notify_vehicle_sold:
    description: |
      Notify TxDMV that you've sold a vehicle. 
      This can be done online via the TxDMV website.
    readonly: false
    params:
      vin: Vehicle Identification Number // "1HGCM82633A123456"
      plate: License plate number // "ABC1234"
      sale_date: Date of sale // "2025-01-15"
      buyer_name?: Buyer's name (optional) // "John Buyer"
      sale_price?: Sale price (optional) // 15000
      odometer?: Odometer reading // 45000
    
    steps:
      - id: submit_notification
        playwright:
          url: https://webdealer.txdmv.gov/title/publicVehicleTransfer
          steps:
            - fill:
                selector: "#vin"
                value: "{{params.vin}}"
            - fill:
                selector: "#plateNumber"
                value: "{{params.plate}}"
            - fill:
                selector: "#saleDate"
                value: "{{params.sale_date | date: '%m/%d/%Y'}}"
            - fill:
                selector: "#buyerName"
                value: "{{params.buyer_name}}"
            - fill:
                selector: "#salePrice"
                value: "{{params.sale_price}}"
            - fill:
                selector: "#odometer"
                value: "{{params.odometer}}"
            - click:
                selector: "#submitButton"
            - wait_for:
                selector: ".confirmation-message"
                timeout: 30000
            - extract:
                confirmation_number: ".confirmation-number"
                status: ".status-message"
    
    response:
      mapping:
        status: "{{submit_notification.status}}"
        confirmation_number: "{{submit_notification.confirmation_number}}"

  # ============================================================
  # COUNTY OFFICE LOOKUP
  # ============================================================
  find_county_office:
    description: Find the county tax office address for vehicle registration
    readonly: true
    params:
      county?: County name // "Dallas"
      zip_code?: ZIP code to lookup county // "75201"
      address?: Full address to extract county // "456 Oak Ave, Dallas TX 75201"
    
    steps:
      - id: determine_county
        choose:
          - when: "{{params.county}}"
            set: { county: "{{params.county}}" }
          - when: "{{params.zip_code}}"
            sql:
              database: "{{agentos_data_dir}}/reference/texas_counties.db"
              query: "SELECT county_name FROM zip_to_county WHERE zip = '{{params.zip_code}}'"
          - when: "{{params.address}}"
            set: { county: "{{params.address | county_from_zip}}" }
      
      - id: lookup
        sql:
          database: "{{agentos_data_dir}}/reference/texas_counties.db"
          query: |
            SELECT 
              county_name,
              tax_office_name,
              tax_office_address,
              tax_office_city,
              tax_office_state,
              tax_office_zip,
              tax_office_phone,
              tax_office_hours,
              tax_office_website
            FROM county_tax_offices
            WHERE county_name = '{{determine_county.county}}'
    
    response:
      mapping:
        county: "[0].county_name"
        name: "[0].tax_office_name"
        address: "[0].tax_office_address"
        city: "[0].tax_office_city"
        zip: "[0].tax_office_zip"
        phone: "[0].tax_office_phone"
        hours: "[0].tax_office_hours"
        website: "[0].tax_office_website"

  # ============================================================
  # CHECK SUBMISSION STATUS
  # ============================================================
  check_status:
    description: Check the status of a previously submitted form
    readonly: true
    params:
      tracking_id?: Lob tracking ID // "ltr_abc123"
      submission_id?: Internal submission ID // 42
    
    steps:
      - id: get_submission
        sql:
          database: "{{agentos_data_dir}}/agentos.db"
          query: |
            SELECT * FROM form_submissions 
            WHERE tracking_id = '{{params.tracking_id}}'
               OR id = '{{params.submission_id}}'
            ORDER BY submitted_at DESC
            LIMIT 1
      
      - id: check_lob_status
        skip_if: "{{not get_submission.tracking_id}}"
        rest:
          method: GET
          url: "https://api.lob.com/v1/letters/{{get_submission.tracking_id}}"
          response:
            mapping:
              mail_status: ".send_date"
              expected_delivery: ".expected_delivery_date"
              carrier: ".carrier"
              tracking_events: ".tracking_events"
    
    response:
      mapping:
        form_type: "{{get_submission.form_type}}"
        status: "{{check_lob_status.mail_status | default: get_submission.status}}"
        submitted_at: "{{get_submission.submitted_at}}"
        tracking_id: "{{get_submission.tracking_id}}"
        expected_delivery: "{{check_lob_status.expected_delivery}}"
        tracking_events: "{{check_lob_status.tracking_events}}"

  # ============================================================
  # LIST MY SUBMISSIONS
  # ============================================================
  list_submissions:
    description: List all form submissions
    readonly: true
    params:
      limit?: Max results // 20
      status?: Filter by status // "mailed" | "delivered" | "pending"
    
    steps:
      - id: query
        sql:
          database: "{{agentos_data_dir}}/agentos.db"
          query: |
            SELECT * FROM form_submissions
            WHERE 1=1
            {{#if params.status}}AND status = '{{params.status}}'{{/if}}
            ORDER BY submitted_at DESC
            LIMIT {{params.limit | default: 20}}
    
    response:
      root: "query"
      mapping:
        id: "[].id"
        form_type: "[].form_type"
        status: "[].status"
        tracking_id: "[].tracking_id"
        submitted_at: "[].submitted_at"
        county: "[].county"

  # ============================================================
  # GENERATE FORM ONLY (No mail)
  # ============================================================
  generate_form:
    description: |
      Generate a filled PDF form without mailing.
      Use this if you want to review/sign manually.
    readonly: true
    params:
      form: Which form to generate // "vtr-146" | "vtr-60" | "vtr-34"
      data: Form field data as object // {"owner_name": "John", "vin": "..."}
      include_signature?: Add signature image // true
      output_path?: Where to save // "~/Desktop/my_form.pdf"
    
    steps:
      - id: get_form_template
        choose:
          - when: "{{params.form == 'vtr-146'}}"
            set: 
              url: "https://www.txdmv.gov/sites/default/files/form_files/VTR_146.pdf"
              name: "Change of Address"
          - when: "{{params.form == 'vtr-60'}}"
            set:
              url: "https://www.txdmv.gov/sites/default/files/form_files/VTR-60.pdf"
              name: "Replacement Sticker"
          - when: "{{params.form == 'vtr-34'}}"
            set:
              url: "https://www.txdmv.gov/sites/default/files/form_files/VTR-34.pdf"
              name: "Certified Copy of Title"
      
      - id: download
        http:
          method: GET
          url: "{{get_form_template.url}}"
          save_to: "{{temp_dir}}/{{params.form}}_blank.pdf"
      
      - id: fill
        pdf:
          action: fill
          template: "{{download.path}}"
          output: "{{params.output_path | default: temp_dir + '/' + params.form + '_filled.pdf'}}"
          fields: "{{params.data}}"
      
      - id: add_sig
        skip_if: "{{not params.include_signature}}"
        pdf:
          action: stamp
          input: "{{fill.output}}"
          stamp: "{{profile.documents.signature.image_path}}"
          output: "{{fill.output | replace: '_filled' : '_signed'}}"
          position:
            page: 1
            x: 400
            y: 650
            width: 150
            height: 50
    
    response:
      mapping:
        form_name: "{{get_form_template.name}}"
        pdf_path: "{{add_sig.output | default: fill.output}}"
        signed: "{{params.include_signature | default: false}}"
---

# Texas DMV

Submit Texas vehicle registration forms, address changes, and more — automatically filled, validated, and mailed.

## How It Works

1. **You provide:** Vehicle info + new address
2. **AgentOS:** Fills the official TxDMV form
3. **Vision AI:** Validates every field looks correct
4. **Signature:** Adds your signature (image or autopen service)
5. **Physical Mail:** Sends to your county tax office via USPS

## Setup

### 1. Add Your Signature

Save a PNG of your signature:
```
~/.agentos/profile/signature.png
```

Tips for a good signature image:
- Sign on white paper with black pen
- Scan or photograph with good lighting
- Crop to just the signature (no extra whitespace)
- Save as PNG with transparent background (ideal) or white background

### 2. Configure Mail Service

Get a Lob API key from https://dashboard.lob.com and add it in AgentOS Settings.

### 3. Update Your Profile

Make sure your AgentOS profile has:
- Full legal name (as it appears on registration)
- Current address
- Vehicle information (optional, for quick access)

## Supported Forms

| Form | Action | Description |
|------|--------|-------------|
| VTR-146 | `update_address` | Change address on registration |
| VTR-60 | `generate_form` | Request replacement sticker |
| VTR-34 | `generate_form` | Request certified copy of title |
| Online | `notify_vehicle_sold` | Vehicle transfer notification |

## Examples

### Change Your Address

```
Apps(
  app: "tx-dot",
  action: "update_address",
  params: {
    vin: "1HGCM82633A123456",
    plate: "ABC1234",
    new_address: "456 Oak Ave, Dallas TX 75201"
  },
  execute: true
)
```

### Generate Form Without Mailing

```
Apps(
  app: "tx-dot", 
  action: "generate_form",
  params: {
    form: "vtr-146",
    data: {
      owner_name: "Joe Smith",
      vin: "1HGCM82633A123456",
      ...
    },
    include_signature: false
  }
)
```

### Find Your County Office

```
Apps(
  app: "tx-dot",
  action: "find_county_office",
  params: { zip_code: "75201" }
)
```

## Signature Options

| Option | How It Works | Acceptance Rate |
|--------|--------------|-----------------|
| `"image"` | Your signature PNG overlaid on PDF | ~80% |
| `"autopen"` | Wet ink via autopen service | ~99% |
| `"none"` | Generate unsigned PDF for manual signing | 100% |

## Validation

Every form is checked by vision AI before mailing:

- **Truncation:** Text cut off in boxes
- **Overflow:** Text outside boundaries  
- **Font Size:** Too small or too large
- **Date Format:** Must be MM/DD/YYYY
- **Missing Fields:** Required fields empty
- **Alignment:** Text readable and positioned correctly

If validation fails, the plugin automatically adjusts (smaller font, etc.) and retries up to 3 times.

## Costs

| Service | Cost |
|---------|------|
| Lob First-Class Letter | ~$1.00 |
| Autopen Signature (optional) | ~$2-5 |
| Vision API Validation | ~$0.01-0.05 |

**Total:** ~$1-6 per form submission

## FAQ

**Q: Is this legal?**
A: Yes. You're filling out official forms with your own information and signature. The autopen is your authorized signature reproduction (same as executives and politicians use).

**Q: What if the county rejects it?**
A: Worst case, they mail it back and ask you to resubmit. There's no penalty for a rejected form. You can always fall back to `signature_type: "none"` and sign manually.

**Q: How long does it take?**
A: Lob mails within 1-2 business days. USPS First Class takes 3-5 days. County processing varies (usually 1-2 weeks).

**Q: Can I track my submission?**
A: Yes! Use `check_status` with your tracking ID to see USPS tracking events.
```

---

## Architecture: Executors vs Capabilities

This plugin uses two patterns for getting work done:

### Built-in Executors (in AgentOS Core)

These are protocol handlers built into the Rust core:

| Executor | Purpose | Implementation |
|----------|---------|----------------|
| `pdf:` | Fill forms, add stamps, render to image | Wraps pdftk/qpdf |
| `vision:` | Send images to AI for analysis | Calls vision APIs (uses user's preferred provider) |
| `sql:` | Query databases | Already exists |
| `http:` | Download files | Already exists |
| `command:` | Run CLI tools | Already exists |
| `choose:` | Conditional branching | New |
| `on_failure:` | Retry logic | New |
| `ask:` | Get user input/confirmation/choice | New |

### Capability-Based Connector Calls

These call other plugins that `provide` a capability:

| Capability | Example Providers | How It's Used |
|------------|-------------------|---------------|
| `pdf-forms` | pdf-lib (built-in), pdftk, qpdf, adobe-api | Fill forms, stamp images, inspect fields |
| `mail` | lob, postgrid, click2mail | Send physical mail |
| `signature` | image-stamp, autopen, docusign | Sign documents (may use pdf-forms internally) |
| `vision` | claude, gpt-4v, gemini | Analyze images |

**Why `pdf-forms` is a capability (not built-in):**
- Users may not have `pdftk` or `qpdf` installed
- Cloud APIs (Adobe) are an option for those without local tools
- `pdf-lib` is built into AgentOS as a fallback (no install required)

**Signature providers:**
- `image-stamp` — Uses `pdf-forms` to stamp signature image
- `autopen` — Sends to physical signing service (wet ink)
- `docusign` — Formal e-signature with audit trail

The key difference:
- **Executors** are built into AgentOS core (http, sql, command)
- **Capabilities** are provided by plugins the user has configured

### New Executors Needed

#### `vision:` — Vision Model Calls

```yaml
vision:
  image: path/to/image.png
  # OR
  image_from_pdf:
    path: path/to/doc.pdf
    page: 1
    dpi: 150
  prompt: |
    Your prompt here...
  response:
    parse: json | text
```

Uses user's preferred vision provider (Claude, GPT-4V, Gemini).

#### `choose:` — Conditional Branching

```yaml
choose:
  - when: "{{condition1}}"
    # steps...
  - when: "{{condition2}}"
    # steps...
  - otherwise:
    # default steps...
```

#### `on_failure:` — Retry Logic

```yaml
on_failure:
  max_retries: 3
  retry_with:
    param: "{{adjusted_value}}"
  goto: step_id
```

#### `ask:` — Get User Input

Pauses execution to get input from the user. Multiple types:

**Review (show file, get approval):**
```yaml
ask:
  type: review
  title: "Review before mailing"
  message: "Check this form looks correct."
  file: "{{signed_form.pdf}}"           # Opens in default app (Preview on macOS)
  actions:
    - id: approve
      label: "Looks good"
    - id: cancel
      label: "Cancel"
```

**Confirm (yes/no question):**
```yaml
ask:
  type: confirm
  title: "Send payment?"
  message: "Transfer $500 to {{recipient}}?"
  actions:
    - id: yes
      label: "Yes, send it"
    - id: no
      label: "No, cancel"
```

**Choice (pick from options):**
```yaml
ask:
  type: choice
  title: "Which vehicle?"
  message: "Multiple vehicles found. Which one?"
  options:
    - id: car1
      label: "2020 Tesla Model 3 (ABC1234)"
    - id: car2  
      label: "2021 Ford F-150 (TRK5678)"
```

**Input (free text):**
```yaml
ask:
  type: input
  title: "Reason for change"
  message: "Why are you updating the address?"
  placeholder: "e.g., Moved to new home"
```

**How it works:**

1. AgentOS shows a dialog/notification
2. If `file:` specified, opens in system default app (`open` on macOS)
3. Waits for user response
4. Returns `{response: "action_id"}` or `{response: "user input text"}`
5. Next steps can use `{{step_id.response}}` to branch

**Use cases:**
- Review documents before mailing
- Confirm destructive/expensive actions  
- Disambiguate when multiple items match
- Get additional info not in profile

### Capability Block

Instead of calling a specific plugin:

```yaml
# OLD - tightly coupled to specific provider
autopen:
  service: pioneer_dm
  document: "form.pdf"
  signature_source: "sig.png"

# NEW - capability-based, provider-agnostic
capability: signature
action: sign
params:
  document: "form.pdf"
  signature_source: "sig.png"
  position: {page: 1, x: 400, y: 650}
```

AgentOS resolves `capability: signature` to the user's preferred signature provider:
- User prefers `autopen` → Routes to Pioneer DM / The Addressers
- User prefers `image-stamp` → Uses built-in PDF stamp
- User prefers `docusign` → Creates formal e-signature

The plugin doesn't need to know which — it just says "sign this."

---

## Data Requirements

### Texas Counties Database

Need a SQLite database with 254 Texas counties:

```sql
-- texas_counties.db

CREATE TABLE county_tax_offices (
  county_name TEXT PRIMARY KEY,
  tax_office_name TEXT,
  tax_office_address TEXT,
  tax_office_city TEXT,
  tax_office_state TEXT DEFAULT 'TX',
  tax_office_zip TEXT,
  tax_office_phone TEXT,
  tax_office_hours TEXT,
  tax_office_website TEXT
);

CREATE TABLE zip_to_county (
  zip TEXT PRIMARY KEY,
  county_name TEXT REFERENCES county_tax_offices(county_name)
);
```

### Form Definitions

**Reality check:** We inspected the actual VTR-146 PDF. It IS fillable with human-readable field names:

```
# Discovered via: qpdf --json VTR-146.pdf

Field Name                              Position (points)    Size
─────────────────────────────────────────────────────────────────
First Name or Entity Name               x=32, y=491         192x16
Middle Name                             x=225, y=491        76x16
Last Name                               x=302, y=491        219x17
Current Address                         x=32, y=464         552x17
City                                    x=32, y=437         192x17
State                                   x=225, y=437        76x17
County                                  x=302, y=437        161x18
ZIP                                     x=464, y=437        120x18
Vehicle Identification Number           x=32, y=339         197x18
Current TX License Plate                x=306, y=366        277x17
Address (NEW)                           x=32, y=293         552x18
City_2                                  x=32, y=266         196x17
Date                                    x=391, y=96         184x25

Signature: NO FORM FIELD — blank space at ~x=50, y=85
Page size: 612x792 points (8.5" x 11")
```

**Key insight:** Signature has NO form field — we stamp an image at coordinates.

### Form Definition File

```yaml
# forms/vtr_146.yaml

id: vtr_146
name: "Texas Change of Address (VTR-146)"
source: "https://www.txdmv.gov/sites/default/files/form_files/VTR-146.pdf"
version: "2024-01"
page_size: [612, 792]                 # points (8.5" x 11")
fillable: true                        # Has form fields (vs image-only PDF)

# Discovered field names (use exactly as-is)
fields:
  owner.first:
    pdf_field: "First Name or Entity Name"
    type: text
    required: true
  
  owner.middle:
    pdf_field: "Middle Name"
    type: text
  
  owner.last:
    pdf_field: "Last Name"
    type: text
    required: true
  
  old_address.line1:
    pdf_field: "Current Address"
    type: text
    required: true
  
  old_address.city:
    pdf_field: "City"
    type: text
    required: true
  
  old_address.state:
    pdf_field: "State"
    type: text
    default: "TX"
  
  old_address.county:
    pdf_field: "County"
    type: text
    required: true                    # Important for TX!
  
  old_address.zip:
    pdf_field: "ZIP"
    type: text
    pattern: "^\\d{5}$"
    required: true
  
  vehicle.vin:
    pdf_field: "Vehicle Identification Number"
    type: text
    required: true
    pattern: "^[A-HJ-NPR-Z0-9]{17}$"
  
  vehicle.plate:
    pdf_field: "Current TX License Plate"
    type: text
    required: true
  
  new_address.line1:
    pdf_field: "Address"              # The NEW address field
    type: text
    required: true
  
  new_address.city:
    pdf_field: "City_2"
    type: text
    required: true
  
  new_address.state:
    pdf_field: "State_2"
    type: text
    default: "TX"
  
  new_address.zip:
    pdf_field: "ZIP_2"
    type: text
    required: true
  
  date:
    pdf_field: "Date"
    type: date
    format: "MM/DD/YYYY"
    required: true

# Signature is NOT a form field — stamp image at coordinates
stamps:
  signature:
    type: image
    page: 1
    position:
      x: 50                           # Points from left
      y: 85                           # Points from bottom
      width: 200
      height: 40

# Fields we skip (not required)
ignore:
  - "Title Document"                  # Per Reddit: not needed
  - "Renewal Recipient First Name or Entity Name"  # Only if different person
```

### Two Types of PDFs

| Type | Has Form Fields | How to Fill |
|------|-----------------|-------------|
| **Fillable** | Yes (`fillable: true`) | Use `pdf_field` names directly |
| **Image-only** | No (`fillable: false`) | Stamp text at coordinates |

**For image-only PDFs:**
```yaml
fillable: false

# No pdf_field — use coordinates instead
fields:
  owner_name:
    type: text
    position: {x: 50, y: 680, width: 300}
    font_size: 10
```

### Signature Handling

Signatures are almost never form fields. Always use coordinate-based stamping:

```yaml
stamps:
  signature:
    type: image
    source: "{{profile.documents.signature.image_path}}"
    page: 1
    position: {x: 50, y: 85, width: 200, height: 40}
```

### How to Discover Fields

```bash
# For fillable PDFs — get field names
qpdf --json form.pdf | python3 -c "
import json, sys
for f in json.load(sys.stdin)['acroform']['fields']:
    print(f['fullname'])
"

# For any PDF — get text positions (useful for image-only)
pdftotext -layout -bbox form.pdf -  # Requires poppler
```

---

## Safe Array Resolution Pattern

**CRITICAL:** Never silently pick from arrays. This applies to vehicles, citizenships, residences, phones, bank accounts — anything that could have multiple items.

### The Problem

```yaml
# ❌ DANGEROUS - silently picks first vehicle, could renew wrong registration!
vehicle: "{{profile.vehicles[0]}}"
```

### The Safe Pattern

```yaml
resolve:
  source: profile.vehicles
  select_by:
    - params.vin                  # 1. Explicit value in params (user specified)
    - params.vehicle_label        # 2. Explicit label in params
    - count: 1                    # 3. Only one item (unambiguous)
  on_ambiguous:
    error: "Multiple vehicles found. Please specify which vehicle."
    prompt:
      field: "vehicle_label"
      options: "{{profile.vehicles | map: 'label'}}"
```

### Resolution Order

1. **Explicit param** → User/agent provided the value directly (e.g., `params.vin`)
2. **By label** → User/agent specified which one by name
3. **Singleton** → Only one item exists, no ambiguity
4. **Ask** → Multiple items, no explicit selection → return error with options

### What "on_ambiguous" Returns

```json
{
  "error": "Multiple vehicles found. Please specify which vehicle.",
  "field": "vehicle_label",
  "options": ["Model 3", "F-150"],
  "details": [
    "Model 3 - 2020 Tesla Model 3 (ABC1234)",
    "F-150 - 2021 Ford F-150 (TRK5678)"
  ]
}
```

The agent can then:
1. Read the `notes` field on each vehicle to understand context
2. Ask the user if still unclear: "Which vehicle? Model 3 or F-150?"
3. Re-call with explicit selection: `vehicle_label: "Model 3"`

### The `notes` Field

Instead of rigid "primary" flags, profile items have a free-text `notes` field the AI can read:

```yaml
vehicles:
  - label: "Model 3"
    vin: "..."
    notes: "Daily driver. Use for commuting - cheaper per mile."
  - label: "F-150"
    vin: "..."
    notes: "Road trips, hauling. Also Smith Consulting LLC company truck."
```

The AI reads the notes to understand context. If a user says "renew my work truck registration", the AI can infer F-150 from the notes. If still ambiguous, it asks.

### Applies To Everything

This pattern applies to ALL arrays in profile:

| Array | Could Have Multiple | Must Resolve Safely |
|-------|---------------------|---------------------|
| `vehicles` | Yes | ✓ |
| `addresses.previous` | Yes | ✓ |
| `residences.history` | Yes | ✓ |
| `documents.passports` | Yes (dual citizens) | ✓ |
| `financial.bank_accounts` | Yes | ✓ |
| `financial.credit_cards` | Yes | ✓ |
| `contact.phone` | Yes (mobile, home, work) | ✓ |
| `citizenship` | Yes (dual/triple citizens) | ✓ |
| `loyalty.airlines` | Yes | ✓ |

---

## What This Enables

With this plugin, a user could say:

> "I just moved to Dallas. Update my car registration address."

And the AI agent would:

1. Get their vehicle info from profile (or ask)
2. Call `Apps(app: "tx-dot", action: "update_address", ...)`
3. The plugin fills the form, validates, signs, mails
4. Returns tracking info
5. User gets confirmation: "Done! Tracking ID: ltr_abc123, expected delivery: Jan 20-23"

**Total human effort:** One sentence.

**What used to take:** Download form → Print → Fill by hand → Sign → Find envelope → Find stamp → Look up address → Mail → Hope it works.
