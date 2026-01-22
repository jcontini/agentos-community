---
id: local
name: Local Storage
description: Local filesystem operations via standard CLI tools
icon: icon.svg
color: "#007AFF"
tags: [files, filesystem]

website: https://support.apple.com/guide/mac-help/organize-files-folders-mac-mchlp2605/mac
platform: macos

# No auth block = no credentials needed (local system access)

instructions: |
  macOS connector for local file operations using standard CLI tools.
  
  **Tools used:** ls, cat, cp, mv, rm, mkdir, tee, file, open, tree, pdftotext, textutil
  
  **Optional dependencies:**
  - `tree` for tree view: `brew install tree`
  - `pdftotext` for PDFs: `brew install poppler`
  
  **Security:**
  - All CLI tools prompt for approval on first use via firewall
  - No shell - all commands executed safely via std::process::Command

# Action implementations (merged from mapping.yaml)
actions:
  open:
    operation: read
    label: "Open file, URL, or app"
    description: Open a file with default app, launch a URL, or start an application
    command:
      binary: open
      args:
        - "{{params.target}}"
    response:
      raw: true

  browse:
    operation: read
    label: "List directory"
    description: List directory contents
    command:
      binary: ls
      args:
        - "-la"
        - "{{params.path}}"
    response:
      raw: true

  browse_tree:
    operation: read
    label: "Directory tree view"
    description: Show directory as a tree structure
    command:
      binary: tree
      args:
        - "-L"
        - "{{params.depth | default: 3}}"
        - "{{params.path}}"
    response:
      raw: true

  read:
    operation: read
    label: "Read file"
    description: Read file contents
    command:
      binary: cat
      args:
        - "{{params.path}}"
    response:
      raw: true

  read_pdf:
    operation: read
    label: "Read PDF file"
    description: Extract text from PDF file
    command:
      binary: pdftotext
      args:
        - "-layout"
        - "{{params.path}}"
        - "-"
    response:
      raw: true

  decrypt_pdf:
    operation: update
    label: "Decrypt PDF file"
    description: Remove password protection from a PDF (requires password)
    command:
      binary: qpdf
      args:
        - "--password={{params.password}}"
        - "--decrypt"
        - "{{params.path}}"
        - "{{params.output}}"

  read_docx:
    operation: read
    label: "Read Word document"
    description: Extract text from DOCX file
    command:
      binary: textutil
      args:
        - "-convert"
        - "txt"
        - "-stdout"
        - "{{params.path}}"
    response:
      raw: true

  file_info:
    operation: read
    label: "Get file info"
    description: Get file type and metadata
    command:
      binary: file
      args:
        - "-b"
        - "--mime-type"
        - "{{params.path}}"
    response:
      raw: true

  write:
    operation: create
    label: "Write file"
    description: Create or overwrite a file
    command:
      binary: dd
      args:
        - "of={{params.path}}"
        - "status=none"
      stdin: "{{params.content}}"

  mkdir:
    operation: create
    label: "Create directory"
    description: Create directory (and parents if needed)
    command:
      binary: mkdir
      args:
        - "-p"
        - "{{params.path}}"

  move:
    operation: update
    label: "Move file or directory"
    description: Move or rename to new location
    command:
      binary: mv
      args:
        - "{{params.from}}"
        - "{{params.to}}"

  copy:
    operation: create
    label: "Copy file"
    description: Copy file to new location
    command:
      binary: cp
      args:
        - "{{params.from}}"
        - "{{params.to}}"

  copy_recursive:
    operation: create
    label: "Copy directory"
    description: Copy directory recursively
    command:
      binary: cp
      args:
        - "-r"
        - "{{params.from}}"
        - "{{params.to}}"

  delete:
    operation: delete
    label: "Delete file"
    description: Delete a single file
    command:
      binary: rm
      args:
        - "{{params.path}}"

  delete_recursive:
    operation: delete
    label: "Delete directory"
    description: Delete directory and contents
    command:
      binary: rm
      args:
        - "-rf"
        - "{{params.path}}"

  rename:
    operation: update
    label: "Rename file or directory"
    description: Rename in place (provide full destination path)
    command:
      binary: mv
      args:
        - "{{params.path}}"
        - "{{params.to}}"
---

# Local Storage

Access local files using standard CLI tools. Pure command executor - no AppleScript.

**Platform:** macOS, Linux (uses standard POSIX tools)

## Implemented Apps

| App | Status |
|-----|--------|
| Files | ✅ Ready |

## CLI Tools Used

| Tool | Actions |
|------|---------|
| `ls` | browse |
| `tree` | browse_tree (optional) |
| `cat` | read |
| `tee` | write (via stdin) |
| `file` | file_info |
| `cp` | copy, copy_recursive |
| `mv` | move, rename |
| `rm` | delete, delete_recursive |
| `mkdir` | mkdir |
| `open` | open |
| `pdftotext` | read_pdf (optional) |
| `textutil` | read_docx |

## Optional Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| `tree` | Tree view in browse | `brew install tree` |
| `pdftotext` | Read PDF files | `brew install poppler` |
