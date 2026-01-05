---
id: macos
name: macOS
description: macOS filesystem operations via standard CLI tools
icon: icon.svg
color: "#007AFF"

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
---

# macOS Connector

Access files using standard CLI tools. Pure command executor - no AppleScript.

**Platform:** macOS (likely works on Linux too with same tools)

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
