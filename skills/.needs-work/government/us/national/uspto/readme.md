---
depends_on: []
inspired_by: []
---

# IP (Intellectual Property) App with USPTO Connector
**Last Updated:** January 2026

## Quick Start for New Sessions

**Read these files first:**
1. This spec (you're here)
2. `~/.agentos/integrations/CONTRIBUTING.md` — How apps/adapters work
3. `~/.agentos/integrations/apps/web/readme.md` — Similar "search external API" pattern

**Related Linear issues:**
- None yet

**API Documentation:**
- USPTO Open Data Portal: https://data.uspto.gov/apis
- TSDR API (Trademarks): https://developer.uspto.gov/api-catalog/tsdr-data-api
- Swagger UI: https://data.uspto.gov/swagger/index.html

---

## Executive Summary

**The problem:** Can't search patents or trademarks from AI. Intellectual property research requires manually navigating USPTO websites.

**The solution:** Create an IP (Intellectual Property) app with USPTO as the first adapter. Supports both trademark (TSDR) and patent (Open Data Portal) searches.

**Why now:** USPTO provides free REST APIs. Trademarks are the immediate use case.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  IP App (apps/ip/)                                                   │
│  Schema: trademark, patent                                           │
│  Actions: search_trademarks, get_trademark, search_patents, get_patent│
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  USPTO Connector (apps/ip/adapters/uspto/)                         │
│  Auth: API key via X-API-KEY header                                  │
│  Endpoints: TSDR (trademarks), ODP (patents)                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  USPTO APIs                                                          │
│  - TSDR: https://tsdrapi.uspto.gov/ts/cd/...                        │
│  - Patents: https://api.uspto.gov/api/v1/patent/...                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## USPTO API Details

### Authentication

All USPTO APIs require an API key:
- **Header:** `X-API-KEY: <your-key>`
- **Get key:** https://data.uspto.gov/myodp (requires USPTO.gov + ID.me account)

### TSDR (Trademark Status & Document Retrieval)

**Base URL:** `https://tsdrapi.uspto.gov/ts/cd/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/casestatus/sn/{serialNumber}/info.json` | GET | Get trademark by serial number |
| `/casestatus/rn/{registrationNumber}/info.json` | GET | Get trademark by registration number |
| `/casedocs/sn/{serialNumber}/docs.json` | GET | Get documents for a trademark |

**Search:** TSDR doesn't have a search endpoint — use the main USPTO Trademark search or TESS.

### Patent Open Data Portal

**Base URL:** `https://api.uspto.gov/api/v1/patent/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/applications/search` | GET/POST | Search patent applications |
| `/applications/{applicationNumber}` | GET | Get application by number |
| `/applications/{applicationNumber}/documents` | GET | Get documents |
| `/applications/{applicationNumber}/continuity` | GET | Get continuity data |

**Search params:**
- `q` — Query string (simplified query syntax)
- `rows` — Number of results (default 20)
- `start` — Offset for pagination

---

## IP App Schema

```yaml
---
id: ip
name: IP
description: Search patents and trademarks
icon: icon.svg

schema:
  trademark:
    id:
      type: string
      required: true
      description: AgentOS internal ID
    serial_number:
      type: string
      required: true
      description: USPTO serial number (8 digits)
    registration_number:
      type: string
      description: Registration number (if registered)
    mark:
      type: string
      description: The trademark text (word mark)
    mark_type:
      type: enum
      values: [standard_character, design, sound, other]
      description: Type of mark
    status:
      type: string
      description: Current status (REGISTERED, PENDING, ABANDONED, etc.)
    status_date:
      type: datetime
      description: Date of current status
    owner:
      type: string
      description: Current owner name
    owner_address:
      type: string
      description: Owner address
    filing_date:
      type: datetime
      description: Application filing date
    registration_date:
      type: datetime
      description: Registration date (if registered)
    classes:
      type: array
      items: { type: number }
      description: International classes (Nice Classification)
    goods_services:
      type: string
      description: Description of goods/services
    attorney:
      type: string
      description: Attorney of record
    description:
      type: string
      description: Mark description (for design marks)
    image_url:
      type: string
      description: URL to trademark image (for design marks)
    refs:
      type: object
      description: External IDs
    metadata:
      type: object
      description: Additional USPTO data

  patent:
    id:
      type: string
      required: true
      description: AgentOS internal ID
    application_number:
      type: string
      required: true
      description: Patent application number
    patent_number:
      type: string
      description: Patent number (if granted)
    title:
      type: string
      description: Invention title
    abstract:
      type: string
      description: Patent abstract
    status:
      type: string
      description: Application status
    filing_date:
      type: datetime
      description: Filing date
    grant_date:
      type: datetime
      description: Grant date (if granted)
    inventors:
      type: array
      items: { type: string }
      description: Inventor names
    assignee:
      type: string
      description: Patent assignee (owner)
    claims_count:
      type: number
      description: Number of claims
    app_type:
      type: string
      description: Application type (utility, design, plant, etc.)
    refs:
      type: object
      description: External IDs
    metadata:
      type: object
      description: Additional USPTO data

actions:
  # === TRADEMARKS (Priority 1) ===
  
  search_trademarks:
    description: Search trademarks by text, owner, or serial number
    readonly: true
    params:
      query:
        type: string
        required: true
        description: Search query (mark text, owner name, or serial number)
      status:
        type: string
        description: Filter by status (registered, pending, abandoned)
      class:
        type: number
        description: Filter by Nice class
      limit:
        type: number
        default: 20
    returns: trademark[]

  get_trademark:
    description: Get trademark by serial or registration number
    readonly: true
    params:
      serial_number:
        type: string
        description: Serial number (8 digits)
      registration_number:
        type: string
        description: Registration number
    returns: trademark

  # === PATENTS (Priority 2) ===

  search_patents:
    description: Search patent applications
    readonly: true
    params:
      query:
        type: string
        required: true
        description: Search query (title, abstract, inventor, assignee)
      inventor:
        type: string
        description: Filter by inventor name
      assignee:
        type: string
        description: Filter by assignee/owner
      status:
        type: string
        description: Filter by status
      limit:
        type: number
        default: 20
    returns: patent[]

  get_patent:
    description: Get patent by application or patent number
    readonly: true
    params:
      application_number:
        type: string
        description: Application number
      patent_number:
        type: string
        description: Patent number
    returns: patent

instructions: |
  The IP app searches USPTO for patents and trademarks.
  
  **Getting started:**
  1. You need a USPTO API key from https://data.uspto.gov/myodp
  2. Search trademarks: `IP(action: "search_trademarks", adapter: "uspto", params: {query: "APPLE"})`
  3. Get trademark: `IP(action: "get_trademark", adapter: "uspto", params: {serial_number: "85123456"})`
  
  **Notes:**
  - Serial numbers are 8 digits (e.g., "85123456")
  - Use status filter for registered marks only
  - International classes (Nice Classification): 1-45
---

# IP (Intellectual Property)

Search patents and trademarks from USPTO and other registries.

## Quick Start

### Search Trademarks

```
IP(action: "search_trademarks", adapter: "uspto", params: {query: "APPLE"})
IP(action: "search_trademarks", adapter: "uspto", params: {query: "Nike", status: "registered"})
```

### Get Trademark Details

```
IP(action: "get_trademark", adapter: "uspto", params: {serial_number: "85123456"})
IP(action: "get_trademark", adapter: "uspto", params: {registration_number: "1234567"})
```

### Search Patents

```
IP(action: "search_patents", adapter: "uspto", params: {query: "machine learning"})
IP(action: "search_patents", adapter: "uspto", params: {assignee: "Apple Inc"})
```

## Nice Classification

Trademarks are classified by goods/services type:

| Class | Category |
|-------|----------|
| 9 | Computers, software, electronics |
| 25 | Clothing, footwear, headwear |
| 35 | Advertising, business services |
| 41 | Education, entertainment |
| 42 | Scientific, technology services |

## Connectors

| Connector | Trademarks | Patents | Notes |
|-----------|------------|---------|-------|
| `uspto` | ✅ | ✅ | US Patent and Trademark Office |

Future adapters could include: EPO (European), WIPO (International), Google Patents.
```

---

## USPTO Connector Implementation

```yaml
---
name: USPTO
icon: icon.png

auth:
  type: api_key
  header: X-API-KEY
  label: USPTO API Key
  help_url: https://data.uspto.gov/myodp
  help_text: |
    Get your API key:
    1. Create USPTO.gov account at https://data.uspto.gov/myodp
    2. Verify identity with ID.me
    3. Your API key will appear on the MyODP page

actions:
  # === TRADEMARK ACTIONS ===

  get_trademark:
    # By serial number
    - when: "{{params.serial_number}}"
      rest:
        method: GET
        url: "https://tsdrapi.uspto.gov/ts/cd/casestatus/sn/{{params.serial_number}}/info.json"
        headers:
          X-API-KEY: "{{auth.api_key}}"
        response:
          root: "trademarkBag.0"
          mapping:
            id: ".serialNumber"
            serial_number: ".serialNumber"
            registration_number: ".registrationNumber"
            mark: ".markElement.characterMark"
            mark_type: |
              .markElement.markCategory == 'Standard Characters' ? 'standard_character' :
              .markElement.markCategory == 'Design' ? 'design' : 'other'
            status: ".statusDescriptionBag.0.statusDescription"
            status_date: ".statusDate"
            owner: ".ownerBag.0.partyName"
            owner_address: ".ownerBag.0.postalAddressBag.0.addressLine"
            filing_date: ".applicationDate"
            registration_date: ".registrationDate"
            classes: ".gsMarkBag[].nicePrimaryClassNumber | to_array"
            goods_services: ".gsMarkBag[].gsDescription"
            attorney: ".staffBag.0.staffName"
            description: ".markElement.markDescription"
            refs:
              serial: ".serialNumber"
              registration: ".registrationNumber"
            metadata:
              raw: "."

    # By registration number
    - when: "{{params.registration_number}}"
      rest:
        method: GET
        url: "https://tsdrapi.uspto.gov/ts/cd/casestatus/rn/{{params.registration_number}}/info.json"
        headers:
          X-API-KEY: "{{auth.api_key}}"
        response:
          root: "trademarkBag.0"
          mapping:
            id: ".serialNumber"
            serial_number: ".serialNumber"
            registration_number: ".registrationNumber"
            mark: ".markElement.characterMark"
            status: ".statusDescriptionBag.0.statusDescription"
            owner: ".ownerBag.0.partyName"
            filing_date: ".applicationDate"
            registration_date: ".registrationDate"
            classes: ".gsMarkBag[].nicePrimaryClassNumber | to_array"
            goods_services: ".gsMarkBag[].gsDescription"

  search_trademarks:
    # Note: TSDR doesn't have a search endpoint
    # This uses the USPTO Trademark Electronic Search System (TESS) indirectly
    # or the new ODP trademark search when available
    rest:
      method: GET
      url: "https://api.uspto.gov/trademark/v1/marks"
      params:
        q: "{{params.query}}"
        status: "{{params.status}}"
        rows: "{{params.limit | default: 20}}"
      headers:
        X-API-KEY: "{{auth.api_key}}"
      response:
        root: "response.docs"
        mapping:
          id: "[].serialNumber"
          serial_number: "[].serialNumber"
          registration_number: "[].registrationNumber"
          mark: "[].wordMark"
          status: "[].status"
          owner: "[].ownerName"
          filing_date: "[].filingDate"
          registration_date: "[].registrationDate"
          classes: "[].internationalClasses | to_array"

  # === PATENT ACTIONS ===

  search_patents:
    rest:
      method: GET
      url: "https://api.uspto.gov/api/v1/patent/applications/search"
      params:
        q: "{{params.query}}"
        inventorName: "{{params.inventor}}"
        assigneeName: "{{params.assignee}}"
        rows: "{{params.limit | default: 20}}"
      headers:
        X-API-KEY: "{{auth.api_key}}"
      response:
        root: "patentBag"
        mapping:
          id: "[].applicationNumberText"
          application_number: "[].applicationNumberText"
          patent_number: "[].patentNumber"
          title: "[].inventionTitle"
          abstract: "[].abstractText"
          status: "[].applicationStatusCode"
          filing_date: "[].filingDate"
          grant_date: "[].grantDate"
          inventors: "[].inventorBag[].inventorName | to_array"
          assignee: "[].assigneeBag.0.assigneeName"
          app_type: "[].applicationTypeCategory"
          refs:
            application: "[].applicationNumberText"
            patent: "[].patentNumber"

  get_patent:
    rest:
      method: GET
      url: "https://api.uspto.gov/api/v1/patent/applications/{{params.application_number | default: params.patent_number}}"
      headers:
        X-API-KEY: "{{auth.api_key}}"
      response:
        root: "."
        mapping:
          id: ".applicationNumberText"
          application_number: ".applicationNumberText"
          patent_number: ".patentNumber"
          title: ".inventionTitle"
          abstract: ".abstractText"
          status: ".applicationStatusCode"
          filing_date: ".filingDate"
          grant_date: ".grantDate"
          inventors: ".inventorBag[].inventorName | to_array"
          assignee: ".assigneeBag.0.assigneeName"
          claims_count: ".claimsCount"
          app_type: ".applicationTypeCategory"
          refs:
            application: ".applicationNumberText"
            patent: ".patentNumber"
          metadata:
            continuity: ".continuityBag"
            documents: ".documentBag"
---

# USPTO

United States Patent and Trademark Office adapter.

## Authentication

USPTO APIs require an API key:

1. Go to https://data.uspto.gov/myodp
2. Create a USPTO.gov account
3. Verify your identity with ID.me (required)
4. Your API key will appear on the MyODP page

## Endpoints Used

| API | Base URL | Purpose |
|-----|----------|---------|
| TSDR | `tsdrapi.uspto.gov` | Trademark status & documents |
| ODP | `api.uspto.gov` | Patent applications |

## Rate Limits

USPTO enforces rate limits per API key. Be mindful of:
- High-volume searches
- Bulk data retrieval

For bulk data, use the USPTO Bulk Data APIs instead.
```

---

## Implementation Steps

### Step 1: Create app structure (30 min)

```bash
mkdir -p ~/.agentos/integrations/apps/ip/adapters/uspto
```

Create:
- `apps/ip/readme.md` — Schema from above
- `apps/ip/icon.svg` — Use Shield or FileText icon from Lucide

### Step 2: Create USPTO adapter (2 hours)

- `apps/ip/adapters/uspto/readme.md` — Auth + action implementations
- `apps/ip/adapters/uspto/icon.png` — USPTO logo

### Step 3: Test TSDR API response (1 hour)

Before implementing, test the actual API responses:

```bash
# Get trademark by serial number
curl -X GET "https://tsdrapi.uspto.gov/ts/cd/casestatus/sn/97654321/info.json" \
  -H "X-API-KEY: YOUR_KEY"
```

Adjust response mappings based on actual JSON structure.

### Step 4: Verify Patent API endpoints (1 hour)

```bash
# Search patents
curl -X GET "https://api.uspto.gov/api/v1/patent/applications/search?q=machine+learning" \
  -H "X-API-KEY: YOUR_KEY"
```

### Step 5: Write tests (2 hours)

Create `apps/ip/tests/ip.test.ts`:

```typescript
import { test, expect } from '../../utils/fixtures';

test.describe('IP App - USPTO', () => {
  test('search_trademarks returns results', async ({ aos }) => {
    const result = await aos.ip.search_trademarks({
      adapter: 'uspto',
      query: 'APPLE',
      limit: 5
    });
    
    expect(result).toBeDefined();
    expect(result.length).toBeGreaterThan(0);
    expect(result[0]).toHaveProperty('serial_number');
    expect(result[0]).toHaveProperty('mark');
  });

  test('get_trademark by serial number', async ({ aos }) => {
    const result = await aos.ip.get_trademark({
      adapter: 'uspto',
      serial_number: '85123456'  // Use a known trademark
    });
    
    expect(result).toBeDefined();
    expect(result.serial_number).toBe('85123456');
  });
});
```

### Step 6: Register with AgentOS (30 min)

The app should auto-register when placed in `~/.agentos/integrations/apps/ip/`.

---

## Design Decisions

### Question: Single "ip" app or separate "patents" and "trademarks" apps?

**Decision: Single "ip" app with multiple schema types**

Rationale:
- USPTO provides both under one API key
- Same adapter can handle both
- "IP" is the natural user mental model
- Future: could add copyrights, trade secrets

### Question: How to handle TSDR's lack of search endpoint?

**Decision: Use USPTO's newer ODP trademark search or document the limitation**

Rationale:
- TSDR only supports get-by-number, not search
- USPTO is migrating to ODP which may have better search
- For now, users can search on USPTO website, get serial number, then use `get_trademark`

### Question: Include document retrieval?

**Decision: Not in v1, add later as `get_trademark_documents`**

Rationale:
- Focus on status/metadata first
- Document retrieval is more complex (PDFs, images)
- Can add as follow-up action

---

## API Response Examples

### TSDR Response (Trademark)

```json
{
  "trademarkBag": [{
    "serialNumber": "85123456",
    "registrationNumber": "1234567",
    "markElement": {
      "characterMark": "EXAMPLE MARK",
      "markCategory": "Standard Characters"
    },
    "statusDescriptionBag": [{
      "statusDescription": "REGISTERED"
    }],
    "applicationDate": "2012-01-15",
    "registrationDate": "2013-05-20",
    "ownerBag": [{
      "partyName": "Example Corporation",
      "postalAddressBag": [{
        "addressLine": "123 Main St, City, ST 12345"
      }]
    }],
    "gsMarkBag": [{
      "nicePrimaryClassNumber": 9,
      "gsDescription": "Computer software..."
    }]
  }]
}
```

### Patent Search Response

```json
{
  "patentBag": [{
    "applicationNumberText": "16/123456",
    "patentNumber": "US10123456",
    "inventionTitle": "Method for Machine Learning",
    "abstractText": "A method for...",
    "applicationStatusCode": "Patented",
    "filingDate": "2020-01-15",
    "grantDate": "2022-05-20",
    "inventorBag": [{
      "inventorName": "John Doe"
    }],
    "assigneeBag": [{
      "assigneeName": "Tech Corp"
    }]
  }]
}
```

---

## Success Criteria

- [ ] Can search trademarks: `IP(action: "search_trademarks", adapter: "uspto", params: {query: "Nike"})`
- [ ] Can get trademark by serial: `IP(action: "get_trademark", adapter: "uspto", params: {serial_number: "..."})`
- [ ] Can get trademark by registration: `IP(action: "get_trademark", adapter: "uspto", params: {registration_number: "..."})`
- [ ] Can search patents: `IP(action: "search_patents", adapter: "uspto", params: {query: "AI"})`
- [ ] Can get patent: `IP(action: "get_patent", adapter: "uspto", params: {application_number: "..."})`
- [ ] Auth works with API key
- [ ] All tests pass

---

## Future Enhancements

### Additional Actions

```yaml
actions:
  get_trademark_documents:
    description: Get documents filed for a trademark
    params:
      serial_number: { type: string, required: true }
    returns: document[]

  get_patent_claims:
    description: Get patent claims text
    params:
      patent_number: { type: string, required: true }
    returns: claim[]

  check_availability:
    description: Quick check if a mark might be available
    params:
      mark: { type: string, required: true }
    returns: { available: boolean, conflicts: trademark[] }
```

### Additional Connectors

| Connector | Region | Notes |
|-----------|--------|-------|
| `epo` | Europe | European Patent Office |
| `wipo` | International | World IP Organization |
| `google-patents` | Global | Aggregated patent search |

---

## References

| Resource | URL |
|----------|-----|
| USPTO Open Data Portal | https://data.uspto.gov/apis |
| TSDR API Docs | https://developer.uspto.gov/api-catalog/tsdr-data-api |
| Patent API Swagger | https://data.uspto.gov/swagger/index.html |
| Nice Classification | https://www.wipo.int/classifications/nice/en/ |
| Get API Key | https://data.uspto.gov/myodp |
