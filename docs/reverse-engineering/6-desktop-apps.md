# Reverse Engineering — macOS Desktop & Electron Apps

When the target is a **desktop app** (Slack, Notion, Granola, VS Code, etc.) that
stores data locally and syncs with a backend. The API is often undocumented;
the app itself is your best source.

This is Layer 6 of the reverse-engineering docs:

- **Layer 1: Transport** — [1-transport.md](1-transport.md) — TLS, headers, WAF bypass
- **Layer 2: Discovery** — [2-discovery.md](2-discovery.md) — web bundles, Apollo cache
- **Layer 3: Auth & Runtime** — [3-auth.md](3-auth.md) — credentials, sessions
- **Layer 4: Content** — [4-content.md](4-content.md) — HTML scraping
- **Layer 5: Social Networks** — [5-social.md](5-social.md) — people, relationships
- **Layer 6: Desktop Apps** (this file) — macOS, Electron, local state, unofficial APIs

---

## When to Use This Approach

| Target | Approach |
|--------|----------|
| Web app (browser-based) | Layers 1–4 — bundles, GraphQL, cookies |
| Desktop app with local data | This doc — app bundle + Application Support |
| Hybrid (web + desktop client) | Both — auth may live in desktop, API is same |

Desktop apps often reuse the **same backend API** as their web counterpart.
The desktop client just embeds a token or session that the web version would
get from a browser cookie flow. If you find the token, you can call the API
directly from Python — no headless browser, no TLS fingerprint games.

---

## Identify the App Stack

### Is it Electron?

```bash
# Check for the telltale structure
ls -la /Applications/SomeApp.app/Contents/Resources/
# Look for: app.asar (bundled JS) or app/ (unpacked)
```

Electron apps ship:
- `app.asar` — compressed archive of the app's JS/HTML
- `Resources/` — icons, native modules
- Chromium runtime inside `Frameworks/`

### Find the app support directory

macOS apps store user data under:

```
~/Library/Application Support/<AppName>/
```

Common subdirs:

| Directory | What it contains |
|-----------|------------------|
| `*.json` (supabase, stored-accounts, local-state) | Auth tokens, config, feature flags |
| `Cache/`, `Code Cache/` | Chromium cache (less useful) |
| `Local Storage/`, `IndexedDB/` | WebStorage — sometimes has SQLite DBs |
| `Session Storage/` | Ephemeral state |
| `blob_storage/` | Binary blobs |
| `*.json` (cache-v6, state) | **Entity cache** — synced from backend, often the gold |

---

## Auth: Steal the Token

Desktop apps must persist auth somewhere. The user is logged in; the app survives
restarts. Find where.

### Common patterns

| File pattern | Typical content |
|--------------|-----------------|
| `supabase.json`, `auth.json`, `tokens.json` | JWT `access_token`, `refresh_token` |
| `stored-accounts.json` | Account list, sometimes with session data |
| `Cookies` (SQLite) | HTTP-only cookies — harder to extract |
| Keychain | macOS Keychain — use `security find-generic-password` |

### Extraction pattern

```python
from pathlib import Path
import json

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "Granola"

def get_token() -> str:
    with open(APP_SUPPORT / "supabase.json") as f:
        data = json.load(f)
    tokens = json.loads(data["workos_tokens"])  # nested JSON string
    return tokens["access_token"]
```

Tokens often live in **nested JSON strings** — the outer file is JSON, but
some values (like `workos_tokens`) are themselves JSON strings. Parse twice.

### Token lifetime

Desktop app tokens are often refreshed by the app when it's running. If your
skill gets `401`, the user needs to **open the app** to refresh. Document this.

---

## Discovery: App Bundle → API Endpoints

The app's bundled JS contains every API endpoint it calls.

### 1. Find the app bundle

```bash
# macOS: find by name
mdfind "kMDItemDisplayName == 'Granola*'"

# Or known paths
ls /Applications/Granola.app/Contents/Resources/app.asar
```

### 2. Extract strings from the bundle

```bash
# If app.asar exists, unpack or search it
npx asar extract /Applications/Granola.app/Contents/Resources/app.asar /tmp/granola-app

# Or just run strings on the binary
strings /Applications/Granola.app/Contents/MacOS/Granola | grep -E "https://|api\.|/v1/|/v2/"
```

### 3. Search for endpoint patterns

| Pattern | What you'll find |
|---------|------------------|
| `https://api.` | Base API URLs |
| `https://notes.` | Web app / docs URLs (often same backend, different frontend) |
| `/v1/`, `/v2/` | Versioned API paths |
| `get-documents`, `get-entity-set` | Endpoint names — these are your operations |

### 4. Infer request shape from usage

Once you have endpoint names, search the bundle for where they're called:

```bash
grep -r "get-entity-set\|get-entity-batch" /tmp/granola-app/
```

The surrounding code often shows the request body shape: `{ entity_type: "chat_thread" }`.

---

## Discovery: Local Cache → Data Model

The app syncs entities from the backend into a local cache. That cache **is**
your schema discovery.

### Find the cache file

Look for large JSON files or SQLite DBs in Application Support:

```bash
ls -la ~/Library/Application\ Support/Granola/
# cache-v6.json    <- 800KB, entities inside
# local-state.json <- feature flags, config
```

### Parse the structure

```python
import json
from pathlib import Path

cache_path = Path.home() / "Library/Application Support/Granola/cache-v6.json"
data = json.loads(cache_path.read_text())

state = data.get("cache", {}).get("state", {})
entities = state.get("entities", {})

# What entity types exist?
print(entities.keys())  # ['chat_thread', 'chat_message']
```

### Infer relationships

From the cache structure:

| Observation | Implication |
|-------------|-------------|
| `chat_thread.data.grouping_key == "meeting:{doc_id}"` | Thread is linked to document |
| `chat_message.data.thread_id == thread.id` | Message belongs to thread |
| `entity.type == "chat_thread"` | API has `entity_type` parameter |

The cache gives you:
- **Entity types** — what to ask the API for
- **Relationships** — how to filter and join
- **Field names** — request/response shape

---

## API Probing: Confirm and Call

You have a token and a list of endpoints. Now validate.

### 1. Reuse existing transport

If the API is behind a plain origin (no CloudFront WAF), `urllib` often works:

```python
from urllib.request import Request, urlopen
import json, gzip

def api_post(token: str, endpoint: str, body: dict):
    req = Request(
        f"https://api.granola.ai{endpoint}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
        },
        method="POST",
    )
    with urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw)
```

If you get `403`, try `httpx` with HTTP/2 (see [1-transport.md](1-transport.md)).

### 2. Probe each endpoint

Start with the simplest call:

```python
# List entities — what does the API return?
resp = api_post(token, "/v1/get-entity-set", {"entity_type": "chat_thread"})
# -> {"data": [{"id": "...", "workspace_id": "...", "created_at": "..."}], "entity_type": "chat_thread"}
```

### 3. Batch fetch for full data

The "set" endpoint usually returns IDs + minimal metadata. The "batch" endpoint
returns full entities:

```python
resp = api_post(token, "/v1/get-entity-batch", {
    "entity_type": "chat_thread",
    "entity_ids": ["uuid-1", "uuid-2"],
})
# -> {"data": [{"id": "...", "data": {"grouping_key": "meeting:doc-id", ...}}, ...]}
```

The `data` field on each entity is where the app-specific payload lives.

---

## End-to-End Flow: Granola Example

1. **Auth** — `~/Library/Application Support/Granola/supabase.json` → `workos_tokens.access_token`
2. **Documents** — `POST /v2/get-documents` (existing), `POST /v1/get-documents-batch`
3. **Transcript** — `POST /v1/get-document-transcript`
4. **Panels** — `POST /v1/get-document-panels` (AI summaries)
5. **Chat threads** — `POST /v1/get-entity-set` + `get-entity-batch` with `entity_type: "chat_thread"`
6. **Chat messages** — same with `entity_type: "chat_message"`
7. **Link** — `chat_thread.data.grouping_key == "meeting:{document_id}"` ties a thread to a meeting

Web URLs (from meeting summaries): `https://notes.granola.ai/t/{thread_id}` — same IDs as API.

---

## API + Cache: Two Connections for Desktop Apps

Desktop apps that sync with a backend often have **two data sources**:

| Source | Where | When to use |
|--------|-------|-------------|
| **API** | Network call with token | Fresh data, full transcripts, works when online |
| **Cache** | Local file (JSON, SQLite) the app writes | Instant, offline, token expired, or fallback |

The app syncs entities into a local cache; that cache is often readable without the token.
You can offer **both** as connections and let the caller choose.

### Connection model

```yaml
connections:
  api:
    description: "Live API — token from app, freshest data"
  cache:
    description: "Local cache — instant, works offline (reads app's cache file)"
```

Operations declare `connection: api` or `connection: cache`. Some operations may
support both; others (e.g. `get_meeting` with full transcript) may be API-only if
the cache doesn't store transcripts.

### When cache is enough

| Operation | API | Cache |
|-----------|-----|-------|
| list_meetings | Yes — paginated from server | Yes — state.documents (may be stale) |
| list_conversations | Yes | Yes — entities.chat_thread filtered by grouping_key |
| get_conversation | Yes | Yes — entities.chat_message by thread_id |
| get_meeting | Yes — full transcript + panels | Partial — cache may have docs but not transcript text |

### Implementation pattern

```python
CACHE_PATH = Path.home() / "Library" / "Application Support" / "Granola" / "cache-v6.json"

def load_cache() -> dict:
    with open(CACHE_PATH) as f:
        return json.load(f)

def cmd_list_conversations_from_cache(document_id: str) -> list:
    data = load_cache()
    threads = (data.get("cache", {}).get("state", {}).get("entities", {}) or {}).get("chat_thread", {})
    target_key = f"meeting:{document_id}"
    out = []
    for tid, t in threads.items():
        if (t.get("data") or {}).get("grouping_key") != target_key:
            continue
        out.append({...})
    return out
```

### Source param: api | cache | auto

For operations that support both, add a `source` param:

- `api` — live call only (default)
- `cache` — local file only
- `auto` — try API, fall back to cache on 401/network error

This gives offline resilience without requiring the user to pick a connection up front.

### Pure-cache skills (WhatsApp, Copilot Money)

Some desktop apps have **no documented API** — the app syncs internally and we only
read the local DB. Those are "cache-only" by necessity:

| Skill | Data source | Pattern |
|-------|-------------|---------|
| WhatsApp | ChatStorage.sqlite | Cache-only |
| Copilot Money | CopilotDB.sqlite | Cache-only |
| Granola | api.granola.ai + cache-v6.json | API + cache |

---

## Subagent Strategy for Exploration

When the codebase is large or you need to search broadly:

1. **Launch an explore subagent** with the app path, cache path, and bundle path.
2. **Tasks:** Extract API URLs from app.asar, parse cache JSON structure, identify entity types and relationships.
3. **Deliverable:** Findings report with endpoints, auth location, data model.

Then implement the skill using those findings. The subagent does the tedious
search-and-document step; you do the clean integration.

---

## Checklist: New Desktop App Skill

| Step | Action |
|------|--------|
| 1 | Find the app: `mdfind` or `ls /Applications/` |
| 2 | Check for Electron: `app.asar` in Resources |
| 3 | Locate Application Support: `~/Library/Application Support/<AppName>/` |
| 4 | Find auth: grep for `token`, `access_token`, `Bearer` in JSON files |
| 5 | Find cache: large JSON or SQLite with `entities`, `state`, `cache` |
| 6 | Parse cache: entity types, relationships, field names |
| 7 | Extract endpoints: `strings` on binary or unpack asar, grep for `https://`, `/v1/` |
| 8 | Probe API: `get-entity-set`, `get-entity-batch` or equivalent with token |
| 9 | Implement: same patterns as web skills — operations, adapters, error handling |

---

## Real-World Examples

| Skill | Discovery path | API + cache |
|-------|----------------|-------------|
| `skills/granola/` | supabase.json token, cache-v6.json entities, app.asar → get-entity-set/batch, grouping_key for meeting→thread link | Yes — api/cache/auto via `source` param |
| `skills/whatsapp/` | ChatStorage.sqlite | Cache-only (no API) |
| `skills/copilot-money/` | CopilotDB.sqlite | Cache-only (no API) |
