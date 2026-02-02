# Notes App

Markdown editor for text files in AgentOS.

## Vision

The Notes app is a simple markdown editor that opens when you click `.md` files in the Files app. It's used for editing profiles, workshop notes, and other text content.

**Comes after:** ui-capabilities (needs solid component foundation first)

**Full spec:** See `agentos/.ROADMAP/todo/files-workspace.md`

---

## Features

- Read/edit markdown files
- Syntax highlighting
- Preview mode (rendered markdown)
- Auto-save
- Opens from Files app when clicking `.md` files

---

## Primary Use Cases

1. **Edit profiles** — `Profiles/goals.md`, `Profiles/work.md`, etc.
2. **Workspace notes** — `Workspace/notes/session.md`
3. **View generated content** — AI-created documents

---

## Related

- **Files app** — Opens Notes when clicking `.md` files
- **Profiles** — User context edited via Notes
- **Workspace** — AI scratchpad with notes

---

## Future: External Note Services

Later, could add connectors for external note services:
- Apple Notes
- Notion
- Obsidian
- Bear

But the primary focus is local `.md` files in AgentOS.
