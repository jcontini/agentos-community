---
depends_on: []
inspired_by:
  - user-profile
---

# PDF Forms Capability Spec

AI-driven form filling that adapts to any PDF — fillable or image-only, any country, any language.

---

## The Problem

### 1. Tools Vary
- `pdftk`, `qpdf` — not installed by default
- Cloud APIs — require accounts
- Connectors shouldn't care which tool is used

### 2. Field Names Are Unreliable

From our research of real government forms:

| Form | Fields | Field Name Quality |
|------|--------|-------------------|
| TX VTR-146 | 30 | ★★★★★ "First Name", "VIN" |
| USCIS I-9 | 130 | ★★★★★ "Last Name (Family)" |
| IRS W4 | 48 | ★☆☆☆☆ "f1_01[0]" garbage |
| CA REG343 | 202 | ☆☆☆☆☆ "Text9.1" useless |
| UK V62 | 0 | N/A - Image-only PDF |
| Japan | 0 | N/A - Image-only, Japanese |

**Only ~25% of forms have useful field names.** Hard-coded mappings would break constantly.

### 3. Forms Change
Government updates PDF → our hard-coded definitions break.

---

## Solution: AI-Driven `pdf-forms` Capability

**Key insight:** Don't hard-code field mappings. Let AI figure it out.

```yaml
capability: pdf-forms
action: fill
params:
  input: "form.pdf"
  output: "filled.pdf"
  
  # Just provide semantic data — AI figures out the mapping
  data:
    owner_name: "Joseph Smith"
    address: "123 Main St, Austin TX 78701"
    vehicle_vin: "1HGCM82633A123456"
    date: "01/15/2025"
  
  # Optional context to help AI
  context: "Texas vehicle registration address change form"
```

**How it works:**

1. **Render** PDF to images (all pages)
2. **Analyze** visually with AI:
   - Find text labels ("Name:", "VIN:", "Address:")
   - Identify fill areas (boxes, lines, empty spaces)
   - Detect checkboxes, signature areas
   - Understand form structure and flow
3. **Match** semantic data to visual fields:
   - "Joseph Smith" → box next to "Owner Name:" label
   - "1HGCM82633A123456" → VIN boxes (may need to split by character)
4. **Fill** using best method:
   - Use form field if exists (even if name is "Text9.1")
   - Stamp text at coordinates if image-only
   - Split into character boxes if needed
5. **Validate** result visually

### Providers

| Provider | Type | AI Support |
|----------|------|------------|
| `pdf-lib` | Built-in | + Vision AI |
| `pdftk` | Local CLI | + Vision AI |
| `adobe-pdf-services` | Cloud API | Has own AI |

---

## Capability Interface

### Actions

| Action | Purpose |
|--------|---------|
| `analyze` | AI analyzes form structure, returns field map |
| `fill` | Fill form (AI-driven or with explicit mappings) |
| `stamp` | Overlay image at coordinates |
| `flatten` | Burn field data into static content |
| `render` | Convert page(s) to images |
| `inspect` | Get raw field names, positions (low-level) |

---

## Action: `analyze` (AI-Driven)

AI analyzes the form visually and returns a semantic field map.

```yaml
capability: pdf-forms
action: analyze
params:
  input: "/path/to/form.pdf"
  context: "Texas DMV address change form"    # Optional hint
```

**Response:**

```json
{
  "page_count": 2,
  "fillable": true,
  "language": "en",
  
  "semantic_fields": [
    {
      "semantic_name": "owner_first_name",
      "label_text": "First Name or Entity Name",
      "page": 1,
      "position": {"x": 32, "y": 491, "width": 192, "height": 16},
      "pdf_field": "First Name or Entity Name",
      "type": "text",
      "required": true
    },
    {
      "semantic_name": "vehicle_vin",
      "label_text": "Vehicle Identification Number",
      "page": 1,
      "position": {"x": 32, "y": 339, "width": 197, "height": 18},
      "pdf_field": "Vehicle Identification Number",
      "type": "text",
      "format": "vin",
      "required": true
    },
    {
      "semantic_name": "signature",
      "label_text": "Owner Signature",
      "page": 1,
      "position": {"x": 50, "y": 85, "width": 200, "height": 40},
      "pdf_field": null,              // No form field — stamp area
      "type": "signature",
      "required": true
    }
  ],
  
  "character_fields": [
    {
      "semantic_name": "license_plate",
      "label_text": "Current TX License Plate",
      "page": 1,
      "pdf_fields": ["0", "2", "3", "4", "5", "6", "7"],  // One per character
      "max_length": 7
    }
  ],
  
  "checkboxes": [
    {
      "semantic_name": "is_new_address",
      "label_text": "Check if this is a new address",
      "page": 1,
      "pdf_field": "CheckBox1",
      "options": ["Yes", "No"]
    }
  ]
}
```

**Key insight:** AI identifies:
- What each field means semantically (not just "Text9.1")
- Where signature areas are (even without form fields)
- Character-by-character fields (VIN, plates)
- Required vs optional fields

---

## Action: `inspect` (Low-Level)

Get raw PDF field data without AI interpretation.

```yaml
capability: pdf-forms
action: inspect
params:
  file: "/path/to/form.pdf"
```

**Response:**

```json
{
  "fillable": true,
  "page_count": 2,
  "page_size": [612, 792],
  
  "raw_fields": [
    {
      "name": "Text9.1",                // Useless name
      "type": "text",
      "page": 1,
      "position": {"x": 32, "y": 491, "width": 192, "height": 16}
    }
    // ... raw field data
  ]
}
```

Use `analyze` instead for AI-interpreted fields.

---

## Action: `fill`

Fill a form intelligently. AI determines how to map data to fields.

### AI-Driven Fill (Recommended)

```yaml
capability: pdf-forms
action: fill
params:
  input: "/path/to/form.pdf"
  output: "/path/to/filled.pdf"
  
  # Semantic data — actual content to place on the form
  data:
    owner_name: "Joseph Smith"
    current_address: "123 Main St, Austin TX 78701"
    new_address: "456 Oak Ave, Dallas TX 75201"
    vehicle_vin: "1HGCM82633A123456"
    license_plate: "ABC1234"
    date_signed: "01/15/2025"
    signature: "/path/to/signature.png"   # Image to stamp
  
  # Hints — guidance for HOW to fill, not WHAT to fill
  hints:
    context: "Texas vehicle address change form"  # Helps AI understand the form
    date_format: "MM/DD/YYYY"                     # How to format dates
    skip_fields: ["Office Use Only"]              # Areas to leave blank
  
  options:
    validate_visually: true
    flatten: false
```

**What happens:**

1. AI analyzes form (or uses cached analysis)
2. Maps `owner_name` → "First Name" + "Last Name" fields (or character boxes)
3. Maps `vehicle_vin` → VIN field(s), splits if needed
4. Maps `license_plate` → plate boxes, one character each
5. Stamps signature at detected signature area
6. Visually validates the result

**Response:**

```json
{
  "success": true,
  "output": "/path/to/filled.pdf",
  "fields_filled": 25,
  "mappings": [
    {"data": "owner_name", "mapped_to": "First Name or Entity Name", "method": "form_field"},
    {"data": "license_plate", "mapped_to": ["0","2","3","4","5","6","7"], "method": "character_split"},
    {"data": "signature", "mapped_to": "page1:x50,y85", "method": "stamp"}
  ],
  "validation": {
    "visual_check": "passed",
    "issues": []
  }
}
```

### Explicit Mode (When AI Can't Figure It Out)

For unusual forms, provide explicit mappings:

```yaml
capability: pdf-forms
action: fill
params:
  input: "weird_form.pdf"
  output: "filled.pdf"
  
  explicit_mappings:
    - pdf_field: "Text9.1"
      value: "J"
    - pdf_field: "Text9.2"
      value: "o"
    - pdf_field: "Text9.3"
      value: "s"
    # ... tedious but precise
    
    - position: {page: 2, x: 100, y: 300}
      value: "Some text"
      method: "stamp"
```

### Handling Different Form Types

| Form Type | AI Approach |
|-----------|-------------|
| Fillable + good names | Direct field fill |
| Fillable + bad names | Position-based matching via AI vision |
| Image-only | Stamp text at AI-detected positions |
| Character boxes | Split values, fill each box |
| Multi-page | Track fields across pages |
| Non-English | AI vision works in any language |

**Response for validation issues:**

```json
{
  "success": false,
  "error": "Could not map all data",
  "unmapped_data": ["middle_name"],
  "suggestions": [
    "Form has no middle name field. Omit or append to first name?"
  ],
  "partial_output": "/path/to/partial.pdf"
}
```

---

## Action: `stamp`

Overlay an image (signature, logo, stamp) at specific coordinates.

```yaml
capability: pdf-forms
action: stamp
params:
  input: "/path/to/filled_form.pdf"
  output: "/path/to/signed_form.pdf"
  
  stamps:
    - image: "/path/to/signature.png"
      page: 1
      position:
        x: 50                       # Points from left
        y: 85                       # Points from bottom
        width: 200
        height: 40
    
    - image: "/path/to/initials.png"
      page: 2
      position: {x: 500, y: 50, width: 30, height: 20}
```

**Response:**

```json
{
  "success": true,
  "output": "/path/to/signed_form.pdf",
  "stamps_applied": 2
}
```

---

## Action: `flatten`

Convert form fields to static content (can't edit anymore).

```yaml
capability: pdf-forms
action: flatten
params:
  input: "/path/to/filled_form.pdf"
  output: "/path/to/final_form.pdf"
```

---

## Action: `render`

Convert PDF page to image (for AI validation).

```yaml
capability: pdf-forms
action: render
params:
  input: "/path/to/form.pdf"
  output: "/path/to/preview.png"
  page: 1
  dpi: 150                          # Resolution
  format: "png"                     # png | jpg
```

---

## Providers

### Provider: `pdftk` (Local CLI)

```yaml
# apps/pdftk/readme.md
id: pdftk
name: pdftk
provides: [pdf-forms]

auth: null                          # No auth — local tool

instructions: |
  Requires pdftk installed locally.
  
  macOS: brew install pdftk-java
  Ubuntu: apt install pdftk
  
actions:
  inspect:
    command: "pdftk {{params.file}} dump_data_fields"
    # Parse output...
  
  fill:
    command: "pdftk {{params.input}} fill_form {{fdf_file}} output {{params.output}}"
    # Generate FDF file from fields...
```

### Provider: `qpdf` (Local CLI)

```yaml
id: qpdf
name: qpdf
provides: [pdf-forms]

instructions: |
  Requires qpdf installed locally.
  macOS: brew install qpdf
```

### Provider: `pdf-lib` (Built-in)

```yaml
id: pdf-lib
name: PDF-Lib (Built-in)
provides: [pdf-forms]

instructions: |
  Built into AgentOS — no installation required.
  Uses pdf-lib JavaScript library.
  
  Limitations:
  - Cannot flatten (use pdftk for that)
  - Limited font support
```

### Provider: `adobe-pdf-services` (Cloud API)

```yaml
id: adobe-pdf-services
name: Adobe PDF Services
provides: [pdf-forms, pdf-ocr, pdf-extract]

auth:
  type: oauth
  # Adobe OAuth flow...

instructions: |
  Cloud-based PDF processing via Adobe.
  Requires Adobe Developer account.
  
  Pricing: ~$0.05 per transaction
```

---

## Provider Selection

User sets preference in profile:

```yaml
preferences:
  providers:
    pdf-forms: "pdf-lib"            # Built-in, no setup
    # OR
    pdf-forms: "pdftk"              # If installed
    # OR  
    pdf-forms: "adobe-pdf-services" # Cloud API
```

AgentOS routes `capability: pdf-forms` to preferred provider.

**Fallback behavior:**
1. Try preferred provider
2. If not available/fails, try next
3. `pdf-lib` is always available (built-in)

---

## Hints & Caching (Optional)

Form definitions are **optional hints**, not requirements.

### Hints File (Optional)

```yaml
# hints/tx_vtr_146.yaml
# These are HINTS — AI can ignore if form changed

form_url: "https://www.txdmv.gov/sites/default/files/form_files/VTR-146.pdf"

hints:
  # Help AI understand context
  form_purpose: "Texas vehicle registration address change"
  
  # Signature area (in case AI can't detect)
  signature_position: {page: 1, x: 50, y: 85, width: 200, height: 40}
  
  # Fields to skip (leave blank)
  skip_fields:
    - label_contains: "Title Document"
    - label_contains: "Office Use"
  
  # Date format preference
  date_format: "MM/DD/YYYY"
  
  # Special handling
  license_plate_format: "character_boxes"  # Split into individual characters
```

**Important:** Hints are suggestions. If form changes, AI adapts — hints don't break anything.

### Analysis Caching

AI analysis results can be cached:

```
~/.agentos/cache/pdf-forms/
  sha256_abc123.json    # Cached analysis for form with hash abc123
```

Cache includes:
- Semantic field map
- Field positions
- Detected signature areas
- Character box groups

Cache is **invalidated** if:
- PDF hash changes (form was updated)
- User requests fresh analysis
- Cache is older than configurable TTL

---

## Example: TX-DOT Using This Capability

```yaml
# In tx-dot adapter

requires:
  pdf-forms: Fill and sign forms
  mail: Send to county office

steps:
  - id: fill_and_sign
    capability: pdf-forms
    action: fill
    params:
      input: "{{download_form.path}}"
      output: "{{temp_dir}}/signed.pdf"
      
      # Semantic data — AI figures out where each goes
      data:
        owner_name: "{{profile.identity.legal_name.full}}"
        current_address: "{{profile.addresses.residence | format_address}}"
        new_address: "{{params.new_address | format_address}}"
        vehicle_vin: "{{resolve_vehicle.vin}}"
        license_plate: "{{resolve_vehicle.plate.number}}"
        date: "{{now | date: 'MM/DD/YYYY'}}"
        signature: "{{profile.documents.signature.image_path}}"
      
      # Hints — guidance for HOW to interpret the form
      hints:
        context: "Texas DMV vehicle registration address change"
        date_format: "MM/DD/YYYY"
      
      options:
        validate_visually: true
        flatten: false
  
  - id: mail_form
    capability: mail
    action: send_letter
    params:
      file: "{{fill_and_sign.output}}"
      to: "{{county_office.address}}"
```

**Key points:**
- No hard-coded field mappings
- AI handles fillable PDFs, image-only PDFs, character boxes, etc.
- Works even if TxDMV updates the form
- Signature automatically placed at detected signature area

---

## Testing

```yaml
# Test AI analysis
capability: pdf-forms
action: analyze
params:
  input: "tests/fixtures/any_government_form.pdf"

expect:
  semantic_fields:
    - semantic_name_contains: "name"
    - semantic_name_contains: "address"
  # Don't test exact field names — they may change!

# Test fill
capability: pdf-forms
action: fill
params:
  input: "tests/fixtures/sample_form.pdf"
  output: "{{temp}}/filled.pdf"
  data:
    owner_name: "Test User"
    date: "01/15/2025"

expect:
  success: true
  fields_filled: "> 0"

# Visual validation test
capability: pdf-forms
action: fill
params:
  input: "tests/fixtures/sample_form.pdf"
  output: "{{temp}}/filled.pdf"
  data: {owner_name: "Test"}
  options:
    validate_visually: true

expect:
  validation:
    visual_check: "passed"
```

---

## Summary

| Aspect | Approach |
|--------|----------|
| **Capability** | `pdf-forms` |
| **Actions** | `analyze`, `fill`, `stamp`, `flatten`, `render`, `inspect` |
| **AI-Driven** | Yes — no hard-coded field mappings |
| **Fillable PDFs** | AI maps semantic data to fields |
| **Image-only PDFs** | AI detects fill areas, stamps text |
| **Character boxes** | AI splits values automatically |
| **Signatures** | AI detects signature area, stamps image |
| **Validation** | Visual AI check of filled result |
| **Hints** | Optional, help AI but don't break if form changes |
| **Caching** | Analysis cached by PDF hash |
| **Default provider** | `pdf-lib` + Vision AI |

### What Makes This Different

**Traditional approach (fragile):**
```yaml
form_def: "vtr_146.yaml"
fields:
  "First Name or Entity Name": "Joseph"  # Breaks if field renamed
```

**AI-driven approach (adaptive):**
```yaml
data:
  owner_name: "Joseph Smith"  # AI figures out where this goes
hints:
  context: "Texas DMV form"   # Optional help
```

Forms can change. AI adapts. Connectors don't break.
