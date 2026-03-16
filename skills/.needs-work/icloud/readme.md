---
id: icloud
name: iCloud
description: Access iCloud Drive as an entity source — files become works, folders become places
icon: icon.svg
color: "#007AFF"
website: https://www.icloud.com

auth:
  type: credentials
  fields:
    - name: username
      type: string
      description: Apple ID email address
    - name: password
      type: string
      secret: true
      description: Apple ID password (or app-specific password if 2FA enabled)

requires:
  - name: pyicloud
    install:
      all: pip install pyicloud

# --- Entity Mapping ---
#
# Files → work subtypes based on extension:
#   .md .txt .pdf .docx .pages .rtf    → document
#   .jpg .png .gif .heic .webp .svg    → image / photo
#   .mp4 .mov .m4v                     → video
#   .mp3 .m4a .wav .aac .flac          → audio
#   everything else                     → work (generic)
#
# Folders → folder (extends place)
#   file_in action → folder contains files and subfolders
#
# NOTE: Polymorphic primary type dispatch (extension → entity type) is not
# yet supported by the engine. Interim: map everything as document with
# data.file_type for the actual type. Migrate when engine supports it.

adapters:
  document:
    mapping:
      id: .docwsid
      title: .name
      url: '"https://www.icloud.com/iclouddrive/" + .docwsid'
      expressed_at: .dateModified
      data.size: .size
      data.extension: .extension
      data.mime_type: .mime_type
      data.file_type: .file_type
      data.etag: .etag
      data.drive_path: .path

      file_in:
        folder:
          id: .parent_id
          name: .parent_name
          path: .parent_path
          source_drive: '"icloud"'

operations:
  # --- Drive browsing ---
  list_documents:
    description: List contents of an iCloud Drive folder (files and subfolders)
    returns: document[]
    params:
      path:
        type: string
        default: /
        description: Folder path (e.g., "/" for root, "/Documents/Projects")
    command:
      binary: python3
      args:
        - "-c"
        - |
          # TODO: implement with scripts/icloud_drive.py wrapper
          print('[]')
      timeout: 30

  get_document:
    description: Get metadata for a specific file in iCloud Drive
    returns: document
    params:
      path:
        type: string
        required: true
        description: Full path to file in iCloud Drive
    command:
      binary: python3
      args:
        - "-c"
        - |
          print('{}')
      timeout: 30

  read_document:
    description: Download and read text content from an iCloud Drive file
    returns: document
    params:
      path:
        type: string
        required: true
    command:
      binary: python3
      args:
        - "-c"
        - |
          print('{}')
      timeout: 60

  # --- Drive mutations ---
  create_document:
    description: Upload a file to iCloud Drive
    returns: document
    params:
      path:
        type: string
        required: true
        description: Destination folder path
      filename:
        type: string
        required: true
      content:
        type: string
        required: true
        description: File content (text files only)
    command:
      binary: python3
      args:
        - "-c"
        - |
          print('{}')
      timeout: 60

  mkdir_document:
    description: Create a new folder in iCloud Drive
    returns: void
    params:
      path:
        type: string
        required: true
        description: Parent folder path
      name:
        type: string
        required: true
    command:
      binary: python3
      args:
        - "-c"
        - |
          print('{}')
      timeout: 30

  rename_document:
    description: Rename a file or folder
    returns: void
    params:
      path:
        type: string
        required: true
      name:
        type: string
        required: true
        description: New name
    command:
      binary: python3
      args:
        - "-c"
        - |
          print('{}')
      timeout: 30

  delete_document:
    description: Move a file or folder to iCloud Drive trash
    returns: void
    params:
      path:
        type: string
        required: true
    command:
      binary: python3
      args:
        - "-c"
        - |
          print('{}')
      timeout: 30
---

# iCloud

iCloud Drive as an entity source for AgentOS. Files become entities in the knowledge graph. Folders become places. Browse, import, and search your iCloud content through the entity graph.

> **Status:** Design spec / needs work
> **Powered by:** [pyicloud](https://github.com/picklepete/pyicloud)
> **Research:** See `icloud-research.md` for deep design analysis

## Requirements

```bash
pip install pyicloud
```

2FA-enabled accounts (most accounts) require one-time verification on first connection. Session caches for ~2 months.

## The Model

```
iCloud Drive                          Entity Graph
─────────────                         ────────────
Documents/                    →       folder (place) "Documents"
  ├── report.pdf              →         ├── file_in → document "report.pdf"
  ├── photo.jpg               →         ├── file_in → image "photo.jpg"
  ├── meeting.mp4             →         ├── file_in → video "meeting.mp4"
  └── Projects/               →         └── file_in → folder (place) "Projects"
       └── spec.md            →              └── file_in → document "spec.md"
```

**Key insight:** Folders are `place` entities (extending the 6th ontological primitive). The `file_in` action — "actor filed item in container" — captures the folder hierarchy as graph edges. An entity can be in multiple places across multiple drives simultaneously.

## Operations

### Browsing

| Operation | Returns | Description |
|-----------|---------|-------------|
| `list_documents` | `document[]` | List folder contents (files + subfolders) |
| `get_document` | `document` | Get file metadata |
| `read_document` | `document` | Download and read text content |

### Mutations

| Operation | Returns | Description |
|-----------|---------|-------------|
| `create_document` | `document` | Upload a file |
| `mkdir_document` | `void` | Create a new folder |
| `rename_document` | `void` | Rename a file or folder |
| `delete_document` | `void` | Move to trash |

## Entity Mapping

Files map to work subtypes based on extension:

| Extension | Entity Type |
|-----------|------------|
| `.md` `.txt` `.pdf` `.docx` `.pages` | document |
| `.jpg` `.png` `.gif` `.heic` `.webp` | image |
| `.mp4` `.mov` `.m4v` | video |
| `.mp3` `.m4a` `.wav` `.flac` | audio |
| Other | work (generic) |

**Note:** Polymorphic primary type dispatch is a pending engine capability. Interim: all items map as `document` with `data.file_type` for the actual type.

## Dependencies

| Dependency | What | Status |
|-----------|------|--------|
| `place` primitive | Folder extends place | Design locked, not yet implemented |
| `file_in` action | Folder → file relationship | Designed in entity-architecture |
| Polymorphic dispatch | Runtime entity type from extension | Not yet in engine |
| pyicloud 2FA integration | Session management for AgentOS | Needs design |

## Related

| Spec | Relevance |
|------|-----------|
| `drives.md` | Cloud drives as entity importers — the architectural foundation |
| `entity-architecture.md` | Place primitive, file_in action, work hierarchy |
| `place-entity.md` | Folder extends place, digital space model |
| `file-handlers.md` | File type → app routing |
| `files-studio.md` | Entity Browser views |
