---
id: here-now
name: here.now
description: "Publish static websites instantly — HTML, images, PDFs — no account needed"
color: "#000000"
website: "https://here.now"
privacy_url: "https://here.now/privacy"
terms_url: "https://here.now/terms"

connections:
  api:
    base_url: https://here.now/api/v1
    auth:
      type: api_key
      header:
        Authorization: '"Bearer " + .auth.key'
    label: API Key
    optional: true
    help_url: https://here.now
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
