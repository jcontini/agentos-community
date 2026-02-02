# Files App

Browse local files across two drives: **AgentOS** and **Macintosh HD**.

## Vision

The Files app is a Finder-like browser for AgentOS. It shows two "drives":

- 💾 **AgentOS** (`~/.agentos/`) — Profiles, Downloads, Workshop, Archive, Data
- 🖴 **Macintosh HD** (`~/`) — User's home folder (opt-in via Settings > Privacy)

**Full spec:** See `agentos/.ROADMAP/todo/files-workspace.md`

---

## Features

- Two-drive interface (AgentOS always accessible, Mac files opt-in)
- Folder browsing with navigation
- File preview based on mime type
- Create/rename/delete operations
- Opens Notes app for `.md` files
- Opens Database app for `.db` files

---

## MCP Tool

```typescript
Files({
  action: "list" | "read" | "write" | "delete",
  drive: "agentos" | "home",  // Which drive
  path: string,               // Path within drive
  content?: string            // For write action
})
```

---

## Related

- **Notes app** — Markdown editor (opens from Files)
- **Database app** — SQLite browser (opens from Files)
- **Workspace** — AI's scratchpad folder within AgentOS drive
