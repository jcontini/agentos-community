# iCloud Adapter — Research

> Design research for modeling iCloud Drive (and iCloud services generally) as entity sources in AgentOS. This document captures the deep thinking — the readme.md is the clean adapter spec.
>
> **Date:** 2026-02-13
> **Context:** First implementation of the "cloud drive as entity importer" pattern from `drives.md`. Folder extends place. Files map to work subtypes. Multi-place relationships are natural in the entity graph.

---

## 1. The Core Model: Drives as Entity Sources

From `drives.md` (2026-02-08 update):

> Cloud drives aren't file browsers — they're **entity importers.** When you "open" a Google Drive file through AgentOS, the adapter imports the content as an entity in your local graph. You get offline access for free.

This means the iCloud adapter is fundamentally a **pull-based importer**, not a real-time sync engine. It reads from iCloud's API and creates/updates entities in the local graph.

### The Import Flow

```
iCloud API (remote)
     │
     ▼
pyicloud (Python library)
     │
     ▼
command executor (JSON output)
     │
     ▼
AgentOS mapping pipeline
     │
     ▼
Entity graph (SQLite)
     │
     ├── document entity (for .md, .pdf, .txt files)
     ├── image entity (for .jpg, .png, .heic files)
     ├── video entity (for .mp4, .mov files)
     ├── audio entity (for .mp3, .m4a files)
     ├── work entity (generic, for unknown types)
     └── folder entity (place — for directories)
          └── file_in relationships → child entities
```

### What "Import" Means

- **Metadata always imported** — name, size, dates, path, etag
- **Text content optionally imported** — for `.md`, `.txt`, `.pdf`, the adapter can extract text and store it in the entity's `content` property. Enables full-text search.
- **Binary content referenced, not stored in DB** — images, videos, audio → content-addressed blobs in `~/.agentos/blobs/{hash}.{ext}` (from drives.md spec)
- **Staleness tracking** — `fetched_at` on every entity. "This document was last fetched from iCloud 2 hours ago."
- **Source provenance** — `source_adapter: "icloud"` on every entity. Enables the `I:` drive tab filter in the Entity Browser.

---

## 2. Folder as Place — Why This Is Right

The `place-entity.md` spec established that `place` is the 6th ontological primitive — "where things exist or happen." The spec explicitly says:

> A YouTube channel and a city are both places. Both contain things (videos / buildings). Both have names, descriptions, and boundaries.

A folder fits this pattern exactly:

| Property | YouTube Channel | City | iCloud Drive Folder |
|----------|----------------|------|---------------------|
| Contains things | Videos | Buildings | Files |
| Has a name | @3blue1brown | Quito | Documents |
| Has hierarchy | Channel → Playlist | Country → State → City | Root → Folder → Subfolder |
| Can be navigated into | Browse channel | Visit city | Open folder |
| Things can be added/removed | Upload video | Build house | Save file |
| Has a URL/address | youtube.com/@... | coordinates | icloud.com/iclouddrive/... |

### The `file_in` Action

Already defined in `entity-architecture.md`:

```
file_in — actor filed item in container (extends add)
```

This is literally the action for "a file exists in a folder." The temporal flow principle says the arrow goes from what existed first to what came after — but here it's the action of placing something, so:

```
folder --[file_in]--> document    "this document was filed in this folder"
folder --[file_in]--> image       "this image was filed in this folder"
folder --[file_in]--> folder      "this subfolder was filed in this folder"
```

### Multi-Place Is Natural

Joe's key insight: "Something can be in multiple places. It's just relationships."

In a filesystem, a file lives in exactly one folder. In the entity graph, an entity can have multiple `file_in` relationships pointing to different places. This is already how the graph works — a YouTube video can be in a channel AND multiple playlists simultaneously (see `place-entity.md` computed state examples).

For iCloud Drive specifically, a file IS in one folder (Apple doesn't support hard links in iCloud Drive). But once it's in the entity graph, the user can add it to additional places, tag it, etc. And across drives, the same content from iCloud and Google Drive might be the same entity with two `file_in` relationships to two different folders (one from each drive).

### Folder Hierarchy as Place Containment

```
folder:root (iCloud Drive root)
  ├── file_in → folder:documents (Documents)
  │     ├── file_in → folder:projects (Projects)
  │     │     ├── file_in → document:spec.md
  │     │     └── file_in → document:notes.txt
  │     └── file_in → image:diagram.png
  ├── file_in → folder:desktop (Desktop)
  └── file_in → folder:downloads (Downloads)
```

This is identical to the nesting pattern in `place-entity.md`:

```
contains: server → category → channel → thread     (Discord)
contains: channel → playlist                         (YouTube)
file_in:  folder → folder → document                 (iCloud Drive)
```

### Proposed `folder` Entity Schema

```yaml
# entities/places/folder.yaml
id: folder
extends: place
name: Folder
description: A directory in a drive — a digital place where works are filed

properties:
  path:
    type: string
    description: Full path from drive root (e.g., "/Documents/Projects")
  item_count:
    type: integer
    description: Number of items in this folder
  source_drive:
    type: string
    description: Which drive this folder came from (icloud, gdrive, dropbox, local)

display:
  primary: name
  icon: folder
  sort:
    - field: name
      order: asc
```

**Note:** This entity doesn't need to exist yet — it's a spec for when the entity architecture migration happens. The iCloud adapter can initially use a simpler mapping that doesn't create folder entities, and add them when the `place` primitive ships.

---

## 3. Polymorphic File Typing

### The Problem

When listing an iCloud Drive folder, the adapter gets mixed types back:

```
Documents/
  ├── report.pdf        → should be document entity
  ├── photo.jpg         → should be image entity
  ├── meeting.mp4       → should be video entity
  ├── podcast.mp3       → should be audio entity
  └── unknown.xyz       → should be generic work entity
```

The current adapter mapping pipeline assumes one entity type per `adapters.{type}` section. One API call → one entity type in the response.

### How YouTube Already Handles This

The YouTube adapter already produces **5 different entity types from a single API call** via typed references:

```yaml
adapters:
  video:          # Primary entity type
    mapping:
      # ... video fields ...
      posted_by:          # → creates account entity
        account: { ... }
      posted_in:          # → creates community entity
        community: { ... }
      video_post:         # → creates post entity
        post: { ... }
      transcript_doc:     # → creates document entity
        document: { ... }
```

One `video.get` call creates: 1 video + 1 account + 1 community + 1 post + 1 document = 5 entities.

But here's the difference: YouTube always returns the same primary type (video). The typed references create secondary entities. For iCloud Drive, the **primary type varies** based on what the file is.

### Options for Solving This

**Option A: Python script does the typing, adapter maps generically**

The Python wrapper script examines each file's extension and outputs a `_type` field:

```json
[
  {"_type": "document", "docwsid": "abc", "name": "report.pdf", "size": 12345},
  {"_type": "image", "docwsid": "def", "name": "photo.jpg", "size": 67890},
  {"_type": "folder", "docwsid": "ghi", "name": "Projects", "type": "folder"}
]
```

The Rust engine reads `_type` and routes each item to the correct adapter mapping section. This requires a new feature in the engine — runtime type dispatch based on a field in the response.

**Option B: Everything is `document`, metadata distinguishes**

Map everything as `document` (the broadest work subtype with `content`). Store the actual type in `data.file_type`. The Entity Browser uses `data.file_type` to render the right icon and handle the right way.

Downside: loses composability. A `.jpg` from iCloud wouldn't show up in "all images" queries.

**Option C: Multiple operations per type**

```yaml
operations:
  document.list:  { ... params: { path, type: "document" } }
  image.list:     { ... params: { path, type: "image" } }
  video.list:     { ... params: { path, type: "video" } }
```

Client calls the right one. Downside: can't browse a folder and see everything.

**Option D: Generic `work.list` operation with runtime type dispatch**

The operation returns `work[]` (the base type). The mapping pipeline inspects each item and routes to the appropriate subtype mapping based on extension. This is the cleanest — it says "I'm listing works from this folder, and each work will be typed at runtime."

### Recommendation: Option A or D

Both require a Rust engine enhancement — runtime type dispatch. This is the same problem that playlists face (a playlist can contain videos AND music). The entity-architecture spec already says:

> Queries work polymorphically: "What was added to this playlist?" traverses all `add`-type action edges.

So the engine needs to support polymorphic entity creation from a single operation. This is a foundational capability that iCloud, Google Drive, Dropbox, playlists, albums, and many other cases need.

**For now (in the .needs-work spec):** Map everything as `document` with `data.file_type` for the actual type. Flag the polymorphic dispatch as a dependency. When the engine supports it, migrate to proper runtime typing.

---

## 4. pyicloud API Deep Dive

### Services Available

| Service | Python API | What it provides |
|---------|-----------|------------------|
| **Drive** | `api.drive` | Browse folders, list files, download, upload, create folders, rename, delete |
| **Photos** | `api.photos` | Browse albums (smart + user), iterate photos, download (original/medium/thumb), photo metadata |
| **Calendar** | `api.calendar` | Events by date range, event details |
| **Contacts** | `api.contacts` | All contacts with phone/email |
| **Reminders** | `api.reminders` | Lists and reminders |
| **Find My** | `api.devices` | Device locations, play sound, lost mode |
| **Account** | `api.account` | Account info |
| **Ubiquity** | `api.files` | Legacy file storage (pre-Drive) |

### Drive API Shape

**DriveNode properties:**
- `name` — filename with extension (e.g., "report.pdf")
- `type` — "file" or "folder"
- `size` — bytes (null for folders)
- `date_modified` — UTC datetime
- `date_changed` — UTC datetime
- `date_last_open` — UTC datetime
- `data['docwsid']` — unique document ID
- `data['drivewsid']` — drive workspace ID
- `data['etag']` — version tag for conflict detection
- `data['extension']` — file extension without dot
- `data['zone']` — iCloud zone (com.apple.CloudDocs)

**DriveNode methods:**
- `dir()` → list of child names
- `get_children()` → list of DriveNode objects
- `open(**kwargs)` → Response object (file content)
- `upload(file_object)` → upload to this folder
- `mkdir(name)` → create subfolder
- `rename(name)` → rename this node
- `delete()` → move to trash

**Navigation:**
```python
api.drive['Documents']['Projects']['spec.md']  # Path-based traversal
api.drive.dir()  # ['Documents', 'Desktop', 'Downloads', ...]
```

### Photos API Shape

**PhotoAlbum types:**
- Smart albums: All Photos, Time-lapse, Videos, Slo-mo, Bursts, Favorites, Panoramas, Screenshots, Live, Recently Deleted, Hidden
- User albums: Any user-created album

**PhotoAsset properties:**
- `id` — record name (unique ID)
- `filename` — original filename (base64 decoded)
- `size` — original file size
- `asset_date` — when photo was taken
- `added_date` — when added to library
- `dimensions` — (width, height) tuple
- `versions` — dict of {original, medium, thumb} with url, width, height, size, type

**PhotoAsset methods:**
- `download(version='original')` → Response with stream=True
- `delete()` → moves to Recently Deleted

**Smart albums as entity mapping:**
Smart albums are effectively **saved queries** — they filter by metadata (is_favorite, is_hidden, asset subtype). In the entity graph, these would be computed views, not collection entities. User albums ARE collections — they have explicit membership.

### Photos → Entity Mapping

```
PhotoAlbum (user-created)  →  collection (extends list)  OR  folder (extends place)?
PhotoAsset (photo)         →  photo (extends image, extends work)
PhotoAsset (video)         →  video (extends work)  — Yes, iCloud Photos has videos too!
```

**The photo/video distinction:** pyicloud distinguishes based on `resVidSmallRes` field presence. If video resolution fields exist, it's a video. Otherwise, it's a photo. This is another case of polymorphic typing from a single API.

**Albums as places vs lists:** A photo album could be:
- A `list` (tag/collection) — if we think of it as organizational grouping
- A `place` (folder) — if we think of it as "where photos live"

In Apple's model, a photo can be in multiple albums simultaneously (unlike Drive folders). This is more like tags than folders. Smart albums are definitely computed views (tags). But user albums have explicit add/remove — closer to playlists.

Leaning toward: **user albums = collection (extends list)**, smart albums = computed views (not entities).

---

## 5. Authentication & Session Management

### The 2FA Challenge

Almost all Apple IDs now have 2FA enabled. pyicloud handles this:

```python
api = PyiCloudService('user@apple.com', 'password')

if api.requires_2fa:
    # User gets a code on their Apple device
    code = input("Enter the code: ")
    result = api.validate_2fa_code(code)
    if result:
        api.trust_session()  # Cache trust for ~2 months
```

### Session Persistence (from pyicloud source)

pyicloud stores session state in two places:

1. **Cookies** — `~/.pyicloud/{sanitized_username}` (LWPCookieJar)
   - Contains auth cookies, CSRF tokens
   - Persisted after every request (`save(ignore_discard=True, ignore_expires=True)`)

2. **Session data** — `~/.pyicloud/{sanitized_username}.session` (JSON)
   - `session_token`, `session_id`, `trust_token`, `scnt`, `account_country`
   - Updated from response headers after every request
   - The `trust_token` is what enables session persistence after 2FA

### Session Lifetime

- **Session token:** Valid until Apple invalidates (~2 months with trust)
- **Trust token:** Issued after `trust_session()` call, sent with each auth attempt
- **Cookies:** Persisted with `ignore_expires=True` — pyicloud deliberately keeps expired cookies since Apple's token refresh mechanism uses them

### Session Recovery Flow

```
Start adapter operation
  │
  ├── Cookie file exists?
  │     ├── Yes → Load cookies + session data
  │     │         └── Try validate token
  │     │               ├── Valid → Proceed with operation
  │     │               └── Invalid → Try re-auth with trust token
  │     │                     ├── Success → Proceed
  │     │                     └── Fail → Need 2FA again
  │     └── No → Fresh login needed → Need 2FA
  │
  └── 2FA Required
        └── Surface notification to user
              └── User enters code
                    └── Validate + trust → Save session → Proceed
```

### Integration with AgentOS Credentials

AgentOS already has a credential store. For iCloud:

1. **Apple ID + password** → stored in AgentOS credentials (like any other adapter)
2. **Session cookies + trust token** → stored in pyicloud's default location (`~/.pyicloud/`)
   - OR: custom `cookie_directory` pointing to `~/.agentos/sessions/icloud/`
3. **2FA code** → one-time interactive input

**Setup flow for AgentOS:**

```
1. User adds iCloud adapter in Settings
2. User enters Apple ID + password → stored in credentials
3. Adapter attempts first connection
4. If 2FA required:
   a. AgentOS shows notification: "iCloud needs verification"
   b. User checks Apple device for code
   c. User enters code in AgentOS UI (or via agent prompt)
   d. Session trusted for ~2 months
5. Adapter stores session in ~/.agentos/sessions/icloud/
6. Subsequent calls use cached session
7. When session expires (~2 months), repeat from step 4
```

**Home Assistant precedent:** Home Assistant has a production-grade pyicloud integration that handles this exact flow. Their approach:
- Credentials stored in HA config
- 2FA handled via persistent notification in the HA UI
- Session cached in HA's data directory
- Automatic retry on session expiry with user notification

We can follow the same pattern, adapted to AgentOS's UI.

### App-Specific Passwords

For accounts with 2FA, Apple offers app-specific passwords (generated at appleid.apple.com). These bypass 2FA entirely — no code needed. However, they have limitations:
- Only work with certain services (may not work with all iCloud APIs)
- Need to be generated manually by the user
- Can be revoked individually

This could be a good "easy mode" option: generate an app-specific password, paste it into AgentOS, never deal with 2FA codes again. Worth testing if pyicloud supports this.

---

## 6. Executor Strategy

### Why `command` Executor (Not a New `python` Executor)

The YouTube adapter uses `command` executor with yt-dlp (a Python program). Same pattern works here:

```yaml
operations:
  document.list:
    command:
      binary: python3
      args:
        - "scripts/icloud_drive.py"  # relative to adapter dir
        - "--operation"
        - "list"
        - "--path"
        - "{{params.path}}"
        - "--credentials"
        - "{{auth.username}}:{{auth.password}}"
      timeout: 30
```

A single Python wrapper script (`scripts/icloud_drive.py`) handles:
- Authentication (with session caching)
- Operation dispatch (list, get, download, mkdir, rename, delete)
- JSON output conforming to adapter mapping expectations
- Error handling (session expired, 2FA needed, not found)

### The Wrapper Script Pattern

```python
#!/usr/bin/env python3
"""iCloud Drive wrapper for AgentOS adapter."""

import json
import sys
import os
from pyicloud import PyiCloudService

COOKIE_DIR = os.path.expanduser("~/.agentos/sessions/icloud")

def get_api(username, password):
    """Get authenticated PyiCloudService instance."""
    os.makedirs(COOKIE_DIR, exist_ok=True)
    api = PyiCloudService(username, password, cookie_directory=COOKIE_DIR)
    
    if api.requires_2fa:
        # Output error that AgentOS can surface to user
        print(json.dumps({
            "error": "2fa_required",
            "message": "iCloud requires two-factor authentication. Please verify on your Apple device."
        }))
        sys.exit(1)
    
    return api

def list_folder(api, path):
    """List contents of a folder, output as JSON."""
    node = api.drive
    if path and path != "/":
        for part in path.strip("/").split("/"):
            node = node[part]
    
    items = []
    for child in node.get_children():
        item = {
            "docwsid": child.data.get("docwsid"),
            "name": child.name,
            "type": child.type,  # "file" or "folder"
            "size": child.size,
            "dateModified": str(child.date_modified) if child.date_modified else None,
            "extension": child.data.get("extension", ""),
            "etag": child.data.get("etag"),
            "path": f"{path.rstrip('/')}/{child.name}",
        }
        items.append(item)
    
    print(json.dumps(items))

# ... dispatch based on --operation arg ...
```

### Why Not a `python` Executor?

A dedicated `python` executor would mean:
- The Rust engine embeds or calls Python directly
- Session state managed by the engine
- More complex, more coupling

The `command` executor is simpler — the Python script is self-contained, manages its own sessions, and outputs JSON. The Rust engine doesn't need to know anything about Python or pyicloud. Same pattern as yt-dlp.

**Future option:** If many adapters need Python (Google Drive via `google-api-python-client`, Dropbox via `dropbox` SDK), a shared Python runtime with adapter-specific scripts might be worth it. But that's optimization, not architecture.

---

## 7. Universal Drive Model — Cross-Adapter Patterns

This adapter is the template for all cloud drive adapters. The patterns should generalize.

### Common Operations Across Drives

| Operation | iCloud | Google Drive | Dropbox | OneDrive | S3 |
|-----------|--------|-------------|---------|----------|-----|
| List folder | `api.drive[path].get_children()` | `files.list(q=...)` | `files_list_folder()` | `children` endpoint | `list_objects_v2()` |
| Get file metadata | `api.drive[path]` | `files.get(fileId)` | `get_metadata()` | `item` endpoint | `head_object()` |
| Download file | `node.open()` | `files.get_media(fileId)` | `files_download()` | `content` endpoint | `get_object()` |
| Upload file | `node.upload(f)` | `files.create(media)` | `files_upload()` | `upload` endpoint | `put_object()` |
| Create folder | `node.mkdir(name)` | `files.create(folder)` | `create_folder_v2()` | `children` POST | N/A |
| Rename | `node.rename(name)` | `files.update(name)` | `move_v2()` | `item` PATCH | `copy_object()` + `delete_object()` |
| Delete | `node.delete()` | `files.delete(fileId)` | `delete_v2()` | `item` DELETE | `delete_object()` |

### Common Entity Mapping

All drive adapters should produce the same entity structure:

```
adapter output → entity type (based on file extension)
                → folder entity (for directories)
                → file_in relationships (folder → contents)
                → source_adapter provenance
                → fetched_at staleness
```

The mapping from extension → entity type should be shared code, not duplicated per adapter. Candidates:
- A shared Python utility for command-based adapters
- A Rust-level MIME type → entity type mapping table
- A YAML config file in the adapter or entities directory

### Drive Letter Assignment

From `drives.md`:

```
A:  Entity Graph (everything, always on)
C:  Local filesystem
D:  Dropbox
F:  FTP/SFTP
G:  Google Drive
H:  GitHub
I:  iCloud Drive
O:  OneDrive
S:  S3
```

The letter is a UI concept — mapped from `connects_to` on the adapter. The Entity Browser shows tabs for each enabled drive adapter.

---

## 8. Open Questions (Resolved and Remaining)

### RESOLVED: Folder as place or tag?

**Answer: Place.** Folders are digital places. The `file_in` action captures the relationship. Tags are layered on top by the user. The folder preserves the source structure; tags add new organization. Multi-place relationships are natural in the graph.

### RESOLVED: How does multi-entity creation work?

**Answer: Already solved.** YouTube adapter creates 5 entities from one call via typed references. The same pipeline works for iCloud — a folder listing could create folder entities as typed references from each file. The primary entity is the file/document; the folder is a typed reference with `file_in` relationship.

Actually, it's the reverse: the folder would create the `file_in` relationship. But the point is that typed references already support this pattern.

### RESOLVED: Same adapter or separate for Photos?

**Answer: Same adapter, different operation namespace.** Same pyicloud auth session. `document.*` for Drive, `photo.*` for Photos. This avoids duplicate auth setup.

### REMAINING: Polymorphic primary entity type

When listing a folder, each item should become its own entity type (document, image, video, etc.) based on extension. The current engine assumes one primary type per operation. This needs a Rust enhancement — runtime type dispatch based on a field in the response.

**Interim approach:** Map everything as `document` with `data.file_type`. Migrate when polymorphic dispatch ships.

### REMAINING: Operation naming convention for drives

Options:
- `drive.list` / `drive.get` — generic "drive" namespace
- `document.list` / `image.list` — per-type operations
- `folder.list` / `file.get` — filesystem-inspired naming

The cleanest is probably `drive.list` (list folder contents, returns mixed types) + `drive.get` (get single file, returns typed entity) + `drive.download` (download binary content). The "drive" prefix makes it clear these are drive operations, not document operations. But this requires `drive` to be a recognized operation prefix — it's not an entity type, it's a namespace.

Alternative: Use `folder.list` (list contents of a folder → makes sense as a folder operation) + `document.get` / `image.get` (get typed file → makes sense as entity operation). This fits the entity-level utility pattern.

### REMAINING: Content extraction for text files

Should the adapter extract text content from PDFs, DOCX, etc.? If yes, the Python script needs additional dependencies (pdftotext, python-docx). This is valuable for search but adds complexity.

**Suggestion:** Start with plain text files only (`.md`, `.txt`). Add PDF/DOCX extraction as a phase 2 enhancement, possibly using the same tools as the `local` storage adapter (pdftotext, textutil).

### REMAINING: Incremental sync / change detection

pyicloud doesn't have a "changes since" API. Each listing is a full scan. For large drives, this could be slow. Options:
- etag comparison (skip unchanged files)
- Last-modified date comparison
- Full re-import on each list (simple but wasteful)

For MVP, full listing with etag-based dedup is sufficient. Incremental sync is an optimization for later.

---

## 9. Related Specs and Dependencies

### Direct Dependencies

| Spec | What it provides | Status |
|------|-----------------|--------|
| `entity-architecture.md` | Place primitive, file_in action, work hierarchy | Design locked |
| `place-entity.md` | Folder extends place, digital space model | Design locked |
| `drives.md` | Drive letters, entity importer pattern, A: drive model | Backend done, entity transition pending |
| `video-ecosystem.md` | Multi-entity creation, typed references, polymorphic patterns | Phase 3b in progress |

### Related But Not Blocking

| Spec | Relevance |
|------|-----------|
| `file-handlers.md` | How file types route to apps (open a .pdf → which app?) |
| `files-studio.md` | Entity Browser views — Types, Tags, Timeline, Graph |
| `bundled-content.md` | Documents as entities, export model |
| `relationship-dedup.md` | Needed when re-importing the same folder |
| `agent-entity-tools.md` | How agents interact with entities |

### Needs to Be Built

| Capability | For |
|-----------|-----|
| Polymorphic entity creation from single operation | Mixed-type folder listings |
| `folder` entity schema (extends place) | Folder hierarchy in graph |
| Python session management in command executor | 2FA flow |
| Extension → entity type mapping | File typing |
| Blob storage for binary content | Images, videos from drive |

---

## 10. pyicloud Alternatives and Risks

### Risks with pyicloud

1. **Maintenance:** Last release was Jan 2026 (v2.3.0). But the library has had periods of inactivity before. Apple can change APIs at any time.
2. **Rate limiting:** Apple may throttle heavy API usage. No official rate limits documented.
3. **2FA friction:** Every ~2 months, users need to re-authenticate. This is inherent to Apple's security model.
4. **China mainland:** Different endpoints needed (`china_mainland=True`). pyicloud supports this.

### Alternatives

1. **Native macOS APIs (Swift executor):** Use CloudKit / NSFileManager to access iCloud Drive natively. Pros: no Python dependency, native auth via Keychain. Cons: macOS only, more complex to implement, may not have full Drive API access.

2. **iCloud web scraping:** Direct HTTP requests to icloud.com APIs. This is what pyicloud does under the hood — it reverse-engineers the web app's API calls. We could do this directly in Rust but it's fragile and complex.

3. **Apple's CloudKit JS:** Apple provides a JavaScript API for CloudKit. But it's designed for app developers accessing their own containers, not for accessing a user's iCloud Drive.

**Recommendation:** pyicloud is the right choice for now. It's battle-tested (used by Home Assistant with millions of users), handles the auth complexity, and wraps all the services we need. If Apple breaks the API, we'll need to update regardless of which approach we use.

### Home Assistant as Reference

Home Assistant's `icloud` integration is the most mature production use of pyicloud:
- Handles 2FA via persistent notifications
- Polls devices for location (Find My)
- Manages session persistence and renewal
- ~2.5M installs

Their code is a good reference for production patterns with pyicloud.
