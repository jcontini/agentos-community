---
id: icloud
name: iCloud Drive
description: Browse, read, and write iCloud Drive files through a local pyicloud session. Use when working with files stored in iCloud Drive on this machine.
icon: icon.svg
color: "#007AFF"
website: https://www.icloud.com/iclouddrive

auth:
  optional: true
  help_text: Install pyicloud and create a saved session first with `python3 -m pip install pyicloud` and `icloud --username you@example.com`.
  account_params:
    username:
      type: string
      required: true
      label: Apple ID email
      description: Apple ID email address used by pyicloud
    china_mainland:
      type: boolean
      required: false
      description: Set true for China mainland Apple IDs

adapters:
  document:
    id: .id
    name: .name
    text: '.preview // null'
    url: '.url // null'
    datePublished: '.modified_at // null'
    content: '.content // null'
    data.path: .path
    data.parent_path: '.parent_path // null'
    data.kind: .kind
    data.extension: '.extension // null'
    data.size: '.size // null'
    data.etag: '.etag // null'

operations:
  list_documents:
    description: List files and folders in an iCloud Drive folder
    returns: document[]
    params:
      path:
        type: string
        description: Folder path, for example / or /Documents/Projects
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - list
      stdin: '{params: (.params + {path: (.params.path // "/")})} | tojson'
      timeout: 60

  get_document:
    description: Get metadata for a single iCloud Drive item
    returns: document
    params:
      path:
        type: string
        required: true
        description: Full iCloud Drive path
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - get
      stdin: '{params: .params} | tojson'
      timeout: 60

  read_document:
    description: Read a text file from iCloud Drive
    returns: document
    params:
      path:
        type: string
        required: true
        description: Full iCloud Drive path
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - read
      stdin: '{params: .params} | tojson'
      timeout: 120

  create_document:
    description: Upload a text file to iCloud Drive
    returns: document
    params:
      path:
        type: string
        required: true
        description: Destination folder path
      filename:
        type: string
        required: true
        description: New file name
      content:
        type: string
        required: true
        description: Text content to upload
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - create
      stdin: '{params: .params} | tojson'
      timeout: 120

  create_folder:
    description: Create a folder in iCloud Drive
    returns:
      ok: boolean
      path: string
    params:
      path:
        type: string
        required: true
        description: Parent folder path
      name:
        type: string
        required: true
        description: Name of the new folder
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - mkdir
      stdin: '{params: .params} | tojson'
      timeout: 60

  rename_document:
    description: Rename a file or folder in iCloud Drive
    returns:
      ok: boolean
      old_path: string
      path: string
    params:
      path:
        type: string
        required: true
        description: Existing item path
      name:
        type: string
        required: true
        description: New file or folder name
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - rename
      stdin: '{params: .params} | tojson'
      timeout: 60

  delete_document:
    description: Delete a file or folder from iCloud Drive
    returns:
      ok: boolean
      path: string
    params:
      path:
        type: string
        required: true
        description: Existing item path
      username:
        type: string
        description: Apple ID email address saved in the local pyicloud session
      china_mainland:
        type: boolean
        description: Set true for China mainland Apple IDs
    command:
      binary: python3
      args:
        - ./icloud-drive.py
        - delete
      stdin: '{params: .params} | tojson'
      timeout: 60
---

# iCloud Drive

iCloud Drive through `pyicloud`. This skill intentionally targets the part of the iCloud surface that is most straightforward to make useful in AgentOS right now: drive-style file browsing and text-file reads/writes.

## Setup

1. Install `pyicloud`:
   `python3 -m pip install pyicloud`
2. Create or refresh a saved local session:
   `icloud --username you@example.com`
3. Add the `username` account param when you use the skill

This skill assumes `pyicloud` can reuse a saved local session or keyring entry. It does not collect an Apple ID password directly in skill frontmatter.

## What It Returns

- Files and folders both come back as `document` for now
- The real kind is preserved in `data.kind`
- Paths, sizes, extensions, and etags are preserved in `data.*`
- `read_document` includes full text content for text-ish files

## Why Everything Is `document`

The older draft correctly called out that iCloud folder listings are polymorphic: one folder can contain documents, images, videos, and folders. The current skill contract is easier to keep stable if we map everything through `document` first and preserve the true type in metadata. That makes this skill usable now without blocking on runtime polymorphic dispatch work.

## Limits

- This first pass is centered on iCloud Drive, not Photos, Contacts, or Find My
- `read_document` is best for UTF-8-ish text files; binary files should be treated as metadata-first
- If Apple invalidates the local session, refresh it with the `icloud` CLI and retry

## Additional Reference

For the deeper design notes from the draft research, see `icloud-research.md`.
