---
id: here-now
name: here.now
description: Publish static websites instantly — HTML, images, PDFs — no account needed
icon: icon.svg
color: "#000000"

website: https://here.now
privacy_url: https://here.now/privacy
terms_url: https://here.now/terms

auth:
  header: { Authorization: '"Bearer " + .auth.key' }
  label: API Key
  optional: true
  help_url: https://here.now
# ═══════════════════════════════════════════════════════════════════════════════
# TRANSFORMERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  website:
    id: .slug
    name: .slug
    title: '(.viewer.title? // .slug)'
    url: .siteUrl
    status: 'if .status == "active" then "active" else "pending" end'
    published_at: .updatedAt
    version_id: .currentVersionId
    expires_at: '.expiresAt?'
    data.anonymous: '.anonymous? // false'
    data.claim_token: '.claimToken?'
    data.claim_url: '.claimUrl?'

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  list_websites:
    description: List all your published sites (requires authentication)
    returns: website[]
    rest:
      method: GET
      url: '"https://here.now/api/v1/publishes"'
      response:
        root: /publishes

  create_website:
    description: |
      Publish content to here.now. Handles the full create→upload→finalize flow.
      Returns the live website entity. If published anonymously, entity.data contains
      claim_token and claim_url — show these to the user immediately.
    returns: website
    params:
      content:
        type: string
        required: true
        description: File content to publish (HTML string, markdown, etc.)
      filename:
        type: string
        default: index.html
        description: Filename within the publish (e.g., "index.html", "report.pdf")
      content_type:
        type: string
        default: "text/html; charset=utf-8"
        description: MIME type of the content
      title:
        type: string
        description: Human-readable title shown in the site viewer
      description:
        type: string
        description: Description shown in the site viewer
      ttl:
        type: integer
        description: Time-to-live in seconds (authenticated only, omit for permanent)
    python:
      module: ./publish.py
      function: op_create_website
      args:
        content: .params.content
        filename: '.params.filename // "index.html"'
        content_type: '.params.content_type // "text/html; charset=utf-8"'
        title: .params.title
        description: .params.description
        ttl: .params.ttl
        token: .auth.key
      timeout: 60

  update_website:
    description: Redeploy an existing site with new content
    returns: website
    params:
      slug:
        type: string
        required: true
        description: The site slug to update (e.g., "bright-canvas-a7k2")
      content:
        type: string
        required: true
        description: New file content
      filename:
        type: string
        default: index.html
      content_type:
        type: string
        default: "text/html; charset=utf-8"
      title:
        type: string
    python:
      module: ./publish.py
      function: op_update_website
      args:
        slug: .params.slug
        content: .params.content
        filename: '.params.filename // "index.html"'
        content_type: '.params.content_type // "text/html; charset=utf-8"'
        title: .params.title
        token: .auth.key
      timeout: 60

  delete_website:
    description: Delete a published site (requires authentication)
    returns: void
    params:
      slug:
        type: string
        required: true
        description: The site slug to delete
    rest:
      method: DELETE
      url: '"https://here.now/api/v1/publish/" + .params.slug'
      response:
        static:
          success: 'true'
          id: .params.slug

# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Additional operations that return custom shapes or support lifecycle flows.
  claim:
    description: |
      Claim an anonymous publish to make it permanent. Requires authentication.
      The claim_token is in entity.data.claim_token — returned once at publish time, never again.
    params:
      slug:
        type: string
        required: true
        description: The site slug to claim
      claim_token:
        type: string
        required: true
        description: The one-time claim token from entity.data.claim_token
    returns:
      success: boolean
      slug: string
    rest:
      method: POST
      url: '"https://here.now/api/v1/publish/" + .params.slug + "/claim"'
      body:
        claimToken: .params.claim_token
      response:
        mapping:
          success: 'true'
          slug: .params.slug

  signup:
    description: |
      Send a magic link to the user's email. They click it, land on the here.now
      dashboard, and copy their API key. Then add it to AgentOS credentials for
      permanent publishes (no 24h expiry, 60/hour rate limit).
      After getting the key: POST /sys/accounts { "skill": "here-now", "account": "default", "api_key": "..." }
    auth: none
    params:
      email:
        type: string
        required: true
        description: User's email address
    returns:
      sent: boolean
      message: string
    rest:
      method: POST
      url: '"https://here.now/api/auth/login"'
      body:
        email: .params.email
      response:
        mapping:
          sent: 'true'
          message: '"Check your inbox for a sign-in link from here.now. Click it, then copy your API key from the dashboard and add it to AgentOS credentials for this skill."'

  patch_metadata:
    description: Update site title, description, or TTL without redeploying files
    params:
      slug:
        type: string
        required: true
      title:
        type: string
        description: New title
      description:
        type: string
        description: New description
      ttl:
        type: integer
        description: New TTL in seconds
    returns:
      success: boolean
    rest:
      method: PATCH
      url: '"https://here.now/api/v1/publish/" + .params.slug + "/metadata"'
      body:
        ttlSeconds: '.params.ttl?'
        viewer:
          title: '.params.title?'
          description: '.params.description?'
      response:
        mapping:
          success: 'true'

---

# here.now

Publish static files to the Cloudflare edge instantly — no build step, no deploy config, no account required.

## How It Works

here.now hosts static files (HTML, CSS, JS, images, PDFs, videos) on Cloudflare's global network. Each publish gets its own subdomain:

```
https://bright-canvas-a7k2.here.now/
```

Three-step flow (handled automatically by the skill):
1. **Create** — declare files and get presigned upload URLs
2. **Upload** — PUT content to Cloudflare directly
3. **Finalize** — make it live

## Anonymous vs. Authenticated

| | Anonymous | Authenticated |
|---|---|---|
| Account needed | No | Yes (sign in at here.now) |
| Expiry | 24 hours | Permanent (or custom TTL) |
| Max file size | 250 MB | 5 GB |
| Rate limit | 5/hour | 60/hour |

**Anonymous publishes return a `claim_token` and `claim_url` exactly once.** Store these — they can't be recovered. The user visits the `claim_url` and signs in to keep the site permanently.

## Usage

### Publish an HTML page

```bash
curl -X POST http://localhost:3456/use/here-now/website.create \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<html><body><h1>Hello world</h1></body></html>",
    "title": "My Page",
    "filename": "index.html"
  }'
```

Response:
```json
{
  "id": "bright-canvas-a7k2",
  "url": "https://bright-canvas-a7k2.here.now/",
  "status": "active",
  "data": {
    "anonymous": true,
    "claim_token": "abc123...",
    "claim_url": "https://here.now/claim?slug=bright-canvas-a7k2&token=abc123..."
  }
}
```

### List your sites (authenticated)

```bash
curl http://localhost:3456/mem/websites?refresh=true&skill=here-now
```

### Claim an anonymous publish

```bash
curl -X POST http://localhost:3456/use/here-now/website.claim \
  -H "Content-Type: application/json" \
  -d '{"slug": "bright-canvas-a7k2", "claim_token": "abc123..."}'
```

### Update a site

```bash
curl -X POST http://localhost:3456/use/here-now/website.update \
  -H "Content-Type: application/json" \
  -d '{"slug": "bright-canvas-a7k2", "content": "<html>Updated!</html>"}'
```

## Publishing Other File Types

Change `filename` and `content_type`:

```json
{ "content": "...", "filename": "report.pdf", "content_type": "application/pdf" }
{ "content": "...", "filename": "data.json", "content_type": "application/json" }
```

## Setup (Authenticated)

1. Sign in at [here.now](https://here.now)
2. Copy your API key from the dashboard
3. Add it to AgentOS credentials for the `here-now` skill
