# Internet App

Displays web search results and page content from AI activity.

## The Observation Model

The Internet app is **view-only**. It displays what AI agents do with web capabilities:

```
AI: "Search for Rust tutorials"
     ↓
MCP: web_search tool → Exa plugin → api.exa.ai
     ↓
Activity Log: {capability: "web_search", request: {...}, response: [...]}
     ↓
Internet App: Shows search results in classic UI
```

Users watch AI browse the web. They don't type URLs or submit searches.

---

## Capabilities

| Capability | Description | Display |
|------------|-------------|---------|
| `web_search` | Search the web | Results list with title, URL, snippet |
| `web_read` | Read/scrape a URL | Markdown content viewer |

---

## UI Components

### URL Bar (Display-Only)

Shows what the AI searched or read:

```
┌─────────────────────────────────────────────────────────────────┐
│ ◀ ▶  ⟳  │ 🔍 rust programming tutorials                    │ ⏳ │
└─────────────────────────────────────────────────────────────────┘
```

- **Back/Forward**: Grayed out (or navigates activity history)
- **Refresh**: Decorative (no re-fetch in view-only mode)
- **Search icon**: Indicates search mode vs URL mode
- **Spinner**: Shows when activity is pending
- **Source badge**: Shows which plugin (Exa, Firecrawl, etc.)

### Search Results View

```
┌─────────────────────────────────────────────────────────────────┐
│  ▸ Learn Rust Programming - The Complete Guide                 │
│    example.com/rust-programming                                 │
│    A comprehensive guide to learning Rust...                    │
│  ─────────────────────────────────────────────────────────────  │
│  ▸ The Rust Programming Language                               │
│    doc.rust-lang.org/book/                                      │
│    The official book on the Rust programming language...        │
└─────────────────────────────────────────────────────────────────┘
         Footer: "5 results from Exa • 230ms"
```

### Read View

When AI reads a page with `web_read`:

```
┌─────────────────────────────────────────────────────────────────┐
│ ◀ ▶  ⟳  │ https://doc.rust-lang.org/book/                     │ │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # Understanding Modern Web Development                         │
│                                                                 │
│  Modern web development has evolved significantly...            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         Footer: "Read via Firecrawl • 1.2s"
```

---

## Schemas

### `web_search`

```typescript
// Input (what AI provides)
{ 
  query: string,
  limit?: number,
  live?: boolean     // true = fresh crawl (slower)
}

// Output (what plugin must return)
{ 
  results: {
    url: string      // required
    title: string    // required
    snippet?: string
    published_at?: string
  }[]
}
```

### `web_read`

```typescript
// Input
{ 
  url: string,
  live?: boolean
}

// Output
{
  url: string        // required
  title?: string
  content: string    // required (markdown)
}
```

---

## Example Plugins

| Plugin | Capabilities | Notes |
|--------|--------------|-------|
| **Exa** | `web_search` | AI-native search engine |
| **Firecrawl** | `web_read`, `web_search` | Web scraping service |
| **Serper** | `web_search` | Google search API |
| **Brave Search** | `web_search` | Privacy-focused search |

---

## Activity-Driven Data Flow

The Internet app doesn't fetch data directly. It subscribes to activities:

```typescript
// Internet app subscribes to web activities
useActivityStream(['web_search', 'web_read'])

// When new activity arrives:
// - Update URL bar with request params
// - Render results/content from response
// - Show source plugin in footer
// - Display loading state for pending activities
```

This is the **observation layer** — a beautiful window into AI's web activity.
