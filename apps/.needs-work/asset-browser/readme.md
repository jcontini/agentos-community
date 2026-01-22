---
depends_on: []
inspired_by:
  - ui-capabilities
  - handlers
---

# Asset Browser

Browse and download design assets — icons and fonts — through AgentOS.

## Vision

Developers constantly need icons and fonts. Instead of context-switching to web interfaces, AgentOS provides native apps for browsing design resources. AI can search for icons, preview fonts, and download assets directly.

**Two apps:**
- **Icons** — Browse 200k+ icons from Iconify (Lucide, Material, Heroicons, etc.)
- **Fonts** — Browse 1500+ font families from Google Fonts

**Key insight:** These are just entities like any other. Plugins provide the data, apps display it. The pattern is the same as Browser/Exa or Tasks/Todoist.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           Apps                                   │
│                                                                 │
│     ┌─────────────┐                    ┌─────────────┐          │
│     │  Icons App  │                    │  Fonts App  │          │
│     │             │                    │             │          │
│     │ displays:   │                    │ displays:   │          │
│     │   icon.*    │                    │   font.*    │          │
│     └─────────────┘                    └─────────────┘          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                          Plugins                                 │
│                                                                 │
│     ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│     │  Iconify    │    │Google Fonts │    │  Fontsource │      │
│     │             │    │             │    │             │      │
│     │ provides:   │    │ provides:   │    │ provides:   │      │
│     │   icon.*    │    │   font.*    │    │   font.*    │      │
│     │             │    │             │    │             │      │
│     │ sources:    │    │ sources:    │    │ sources:    │      │
│     │  iconify.   │    │  fonts.     │    │  cdn.fonts  │      │
│     │  design/*   │    │  googleapis │    │  ource.org  │      │
│     └─────────────┘    └─────────────┘    └─────────────┘      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                          Entities                                │
│                                                                 │
│     ┌─────────────┐                    ┌─────────────┐          │
│     │    icon     │                    │    font     │          │
│     └─────────────┘                    └─────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Feature: Plugin Remote Sources

Plugins need to fetch data from remote APIs. For security, plugins must declare allowed sources upfront. Core validates all network requests against this allowlist.

### Plugin Config

```yaml
# plugins/iconify/readme.md
---
id: iconify
name: Iconify
description: 200,000+ icons from 150+ icon sets

# Security: only these URLs can be fetched
sources:
  - https://api.iconify.design/*
  - https://api.simplesvg.com/*

provides:
  - icon.search
  - icon.get
  - icon.list_sets
---
```

### How It Works

1. **Plugin declares `sources`** — glob patterns for allowed URLs
2. **Core validates on load** — rejects plugins with no sources if they use `rest` executor
3. **Core validates on fetch** — every HTTP request checked against sources
4. **Reject unauthorized requests** — return error, don't make the request

### Security Model

| Scenario | Result |
|----------|--------|
| Plugin fetches `https://api.iconify.design/lucide.json` | ✓ Allowed (matches source) |
| Plugin fetches `https://evil.com/steal-data` | ✗ Rejected (no matching source) |
| Plugin has no `sources` but uses `rest` executor | ✗ Rejected on load |
| Plugin with `sources: []` (empty) | Only local operations allowed |

### Implementation Notes

- Sources use glob patterns (`*` matches any path segment)
- Exact domain matching (no subdomain wildcards unless explicit)
- Query strings are part of the URL, included in matching
- Core logs all fetch attempts for audit

---

## Entities

### `icon.yaml`

```yaml
id: icon
name: Icon
description: Vector icon from an icon set

fields:
  # Identity
  id:
    type: string
    required: true
    description: Unique identifier (usually "set:name")
  
  name:
    type: string
    required: true
    description: Icon name (e.g., "calendar", "user", "arrow-right")
  
  set:
    type: string
    required: true
    description: Icon set identifier (e.g., "lucide", "mdi", "heroicons")
  
  set_name:
    type: string
    description: Human-readable set name (e.g., "Lucide", "Material Design Icons")
  
  # Content
  svg:
    type: string
    description: SVG markup (the actual icon)
  
  preview_url:
    type: string
    description: URL to preview image (for list views)
  
  # Metadata
  tags:
    type: array
    items: string
    description: Search keywords and aliases
  
  category:
    type: string
    description: Category within the set (e.g., "arrows", "media", "files")
  
  style:
    type: string
    enum: [outline, filled, duotone, solid, twotone]
    description: Icon style variant
  
  # Dimensions
  width:
    type: integer
    description: Default width in pixels
  
  height:
    type: integer
    description: Default height in pixels
  
  # Source
  author:
    type: string
    description: Icon or set author
  
  license:
    type: string
    description: License (e.g., "MIT", "Apache-2.0", "CC-BY-4.0")
  
  url:
    type: string
    description: URL to icon on source website
```

### `font.yaml`

```yaml
id: font
name: Font
description: Font family for typography

fields:
  # Identity
  id:
    type: string
    required: true
    description: Unique identifier (usually family name slugified)
  
  family:
    type: string
    required: true
    description: Font family name (e.g., "Inter", "Roboto", "JetBrains Mono")
  
  # Classification
  category:
    type: string
    required: true
    enum: [serif, sans-serif, monospace, display, handwriting]
    description: Font category
  
  # Variants
  weights:
    type: array
    items: integer
    description: Available weights (100, 200, 300, 400, 500, 600, 700, 800, 900)
  
  styles:
    type: array
    items: string
    description: Available styles (e.g., ["normal", "italic"])
  
  variable:
    type: boolean
    description: Is this a variable font?
  
  variable_axes:
    type: array
    items: string
    description: Variable font axes (e.g., ["wght", "wdth", "slnt"])
  
  # Preview
  preview_url:
    type: string
    description: URL to font specimen image
  
  preview_text:
    type: string
    description: Sample text for preview (defaults to "The quick brown fox...")
  
  # Download
  download_url:
    type: string
    description: URL to download font files (zip or individual)
  
  formats:
    type: array
    items: string
    description: Available formats (e.g., ["woff2", "woff", "ttf", "otf"])
  
  # Metadata
  designer:
    type: string
    description: Font designer or foundry
  
  license:
    type: string
    description: License (e.g., "OFL", "Apache-2.0")
  
  version:
    type: string
    description: Font version
  
  url:
    type: string
    description: URL to font on source website
  
  # Stats (from Google Fonts API)
  popularity:
    type: integer
    description: Popularity rank (lower = more popular)
  
  trending:
    type: integer
    description: Trending rank
```

---

## Plugins

### Iconify Plugin

```yaml
# plugins/iconify/readme.md
---
id: iconify
name: Iconify
description: 200,000+ icons from 150+ icon sets
icon: iconify

sources:
  - https://api.iconify.design/*

provides:
  - icon.search
  - icon.get
  - icon.list_sets

operations:
  search:
    entity: icon
    operation: search
    description: Search icons across all sets
    params:
      query:
        type: string
        required: true
        description: Search query
      set:
        type: string
        description: Filter by icon set
      style:
        type: string
        enum: [outline, filled, duotone, solid]
      limit:
        type: integer
        default: 64
    rest:
      method: GET
      url: https://api.iconify.design/search
      params:
        query: "{{query}}"
        prefix: "{{set}}"
        limit: "{{limit}}"
      response:
        # Iconify returns: { icons: ["set:name", ...], total: number }
        mapping:
          icons: icons
          total: total

  get:
    entity: icon
    operation: read
    description: Get icon SVG
    params:
      set:
        type: string
        required: true
      name:
        type: string
        required: true
    rest:
      method: GET
      url: "https://api.iconify.design/{{set}}/{{name}}.svg"
      response:
        # Returns raw SVG
        type: raw
        field: svg

  list_sets:
    entity: icon
    operation: list
    description: List available icon sets
    rest:
      method: GET
      url: https://api.iconify.design/collections
      response:
        # Returns object with set info
        mapping:
          sets: "."
---

# Iconify Plugin

Access 200,000+ open source icons from 150+ icon sets through the Iconify API.

## Icon Sets

Popular sets include:
- **Lucide** — Clean, consistent icons (fork of Feather)
- **Material Design Icons** — Google's material icons
- **Heroicons** — From the Tailwind team
- **Phosphor** — Flexible icon family
- **Simple Icons** — Brand/logo icons
- **Tabler Icons** — 4500+ icons
- **Font Awesome Free** — Classic icon set

## Usage

Search for icons:
```
icon.search(query: "calendar")
icon.search(query: "arrow", set: "lucide")
```

Get icon SVG:
```
icon.get(set: "lucide", name: "calendar")
```

## API

Uses the [Iconify API](https://iconify.design/docs/api/). No authentication required.

## License

Icons retain their original licenses. Most are MIT, Apache-2.0, or CC-BY-4.0.
Check individual set licenses before commercial use.
```

### Google Fonts Plugin

```yaml
# plugins/google-fonts/readme.md
---
id: google-fonts
name: Google Fonts
description: 1,500+ free font families
icon: google-fonts

sources:
  - https://www.googleapis.com/webfonts/*
  - https://fonts.googleapis.com/*
  - https://fonts.gstatic.com/*

provides:
  - font.search
  - font.get
  - font.list

auth:
  type: api_key
  key_name: GOOGLE_FONTS_API_KEY
  optional: true  # API works without key, just rate limited

operations:
  search:
    entity: font
    operation: search
    description: Search font families
    params:
      query:
        type: string
        description: Search by family name
      category:
        type: string
        enum: [serif, sans-serif, monospace, display, handwriting]
      sort:
        type: string
        enum: [alpha, date, popularity, style, trending]
        default: popularity
      limit:
        type: integer
        default: 50
    rest:
      method: GET
      url: https://www.googleapis.com/webfonts/v1/webfonts
      params:
        key: "{{credentials.api_key}}"
        sort: "{{sort}}"
      response:
        mapping:
          fonts: items

  get:
    entity: font
    operation: read
    description: Get font details
    params:
      family:
        type: string
        required: true
    rest:
      method: GET
      url: https://www.googleapis.com/webfonts/v1/webfonts
      params:
        key: "{{credentials.api_key}}"
        family: "{{family}}"
      response:
        mapping:
          font: "items[0]"

  list:
    entity: font
    operation: list
    description: List all fonts
    params:
      category:
        type: string
        enum: [serif, sans-serif, monospace, display, handwriting]
      sort:
        type: string
        enum: [alpha, date, popularity, style, trending]
        default: popularity
    rest:
      method: GET
      url: https://www.googleapis.com/webfonts/v1/webfonts
      params:
        key: "{{credentials.api_key}}"
        sort: "{{sort}}"
      response:
        mapping:
          fonts: items
---

# Google Fonts Plugin

Access 1,500+ free font families through the Google Fonts API.

## Usage

Search fonts:
```
font.search(query: "inter")
font.search(category: "monospace", sort: "popularity")
```

List fonts:
```
font.list(category: "sans-serif", sort: "trending")
```

## API Key

Optional. Without a key, requests are rate-limited.
Get a key from [Google Cloud Console](https://console.cloud.google.com/).

## License

All Google Fonts are open source (OFL or Apache-2.0).
```

---

## Apps

### Icons App

```yaml
# apps/icons/app.yaml
id: icons
name: Icons
icon: icons  # need to download an icon for this app
description: Browse and download icons

displays:
  - icon.search
  - icon.get
  - icon.list_sets

views:
  browse:
    title: Icons
    toolbar:
      - component: text-input
        props:
          placeholder: "Search icons..."
          value: "{{activity.request.query}}"
          icon: search
      - component: select
        props:
          placeholder: "All sets"
          value: "{{activity.request.set}}"
          options: "{{sets}}"
      - component: select
        props:
          placeholder: "All styles"
          value: "{{activity.request.style}}"
          options:
            - { value: outline, label: Outline }
            - { value: filled, label: Filled }
            - { value: duotone, label: Duotone }
    
    layout:
      - component: grid
        columns: 8
        gap: 16
        data:
          source: activity
          filter: icon.search
        item_component: items/icon-card
        item_props:
          id: "{{id}}"
          name: "{{name}}"
          set: "{{set}}"
          svg: "{{svg}}"
          preview_url: "{{preview_url}}"
        on_click:
          action: select
          params:
            id: "{{id}}"
    
    footer:
      - component: text
        props:
          content: "{{total}} icons from {{set_name || 'all sets'}}"

  detail:
    title: "{{name}}"
    layout:
      - component: stack
        direction: vertical
        align: center
        gap: 24
        children:
          - component: icon-preview
            props:
              svg: "{{svg}}"
              sizes: [24, 32, 48, 64, 96]
          
          - component: stack
            direction: horizontal
            gap: 12
            children:
              - component: button
                props:
                  label: Copy SVG
                  action: copy
                  value: "{{svg}}"
              - component: button
                props:
                  label: Download
                  action: download
                  filename: "{{name}}.svg"
                  content: "{{svg}}"
          
          - component: key-value
            props:
              items:
                - { key: Name, value: "{{name}}" }
                - { key: Set, value: "{{set_name}}" }
                - { key: Style, value: "{{style}}" }
                - { key: Tags, value: "{{tags | join(', ')}}" }
                - { key: License, value: "{{license}}" }
```

### Fonts App

```yaml
# apps/fonts/app.yaml
id: fonts
name: Fonts
icon: fonts  # need to download an icon for this app
description: Browse and download fonts

displays:
  - font.search
  - font.get
  - font.list

views:
  browse:
    title: Fonts
    toolbar:
      - component: text-input
        props:
          placeholder: "Search fonts..."
          value: "{{activity.request.query}}"
          icon: search
      - component: select
        props:
          placeholder: "All categories"
          value: "{{activity.request.category}}"
          options:
            - { value: serif, label: Serif }
            - { value: sans-serif, label: Sans Serif }
            - { value: monospace, label: Monospace }
            - { value: display, label: Display }
            - { value: handwriting, label: Handwriting }
      - component: select
        props:
          placeholder: "Sort by"
          value: "{{activity.request.sort}}"
          options:
            - { value: popularity, label: Popular }
            - { value: trending, label: Trending }
            - { value: alpha, label: A-Z }
            - { value: date, label: Newest }
    
    layout:
      - component: list
        data:
          source: activity
          filter: font.search
        item_component: items/font-specimen
        item_props:
          family: "{{family}}"
          category: "{{category}}"
          weights: "{{weights}}"
          variable: "{{variable}}"
          preview_text: "The quick brown fox jumps over the lazy dog"
        on_click:
          action: select
          params:
            family: "{{family}}"

  detail:
    title: "{{family}}"
    layout:
      - component: stack
        direction: vertical
        gap: 24
        children:
          - component: font-preview
            props:
              family: "{{family}}"
              weights: "{{weights}}"
              styles: "{{styles}}"
              sample_text: "The quick brown fox jumps over the lazy dog"
          
          - component: stack
            direction: horizontal
            gap: 12
            children:
              - component: button
                props:
                  label: Download
                  action: download
                  url: "{{download_url}}"
              - component: button
                props:
                  label: View on Google Fonts
                  action: open
                  url: "{{url}}"
          
          - component: key-value
            props:
              items:
                - { key: Designer, value: "{{designer}}" }
                - { key: Category, value: "{{category}}" }
                - { key: Weights, value: "{{weights | join(', ')}}" }
                - { key: Variable, value: "{{variable ? 'Yes' : 'No'}}" }
                - { key: License, value: "{{license}}" }
```

---

## UI Components

### `items/icon-card.tsx`

```tsx
interface IconCardProps {
  id: string;
  name: string;
  set: string;
  svg?: string;
  preview_url?: string;
  selected?: boolean;
}

// Grid card showing icon preview
// - Renders SVG inline if provided
// - Falls back to preview_url image
// - Shows name on hover
// - Highlight when selected
```

### `items/font-specimen.tsx`

```tsx
interface FontSpecimenProps {
  family: string;
  category: string;
  weights: number[];
  variable?: boolean;
  preview_text: string;
}

// List item showing font preview
// - Loads font dynamically from Google Fonts CSS
// - Renders preview text in the font
// - Shows metadata (category, weights, variable badge)
```

### `icon-preview.tsx`

```tsx
interface IconPreviewProps {
  svg: string;
  sizes: number[];
}

// Shows icon at multiple sizes for comparison
// - Row of icons: 24px, 32px, 48px, 64px, 96px
// - SVG rendered inline at each size
```

### `font-preview.tsx`

```tsx
interface FontPreviewProps {
  family: string;
  weights: number[];
  styles: string[];
  sample_text: string;
}

// Shows font at different weights
// - Editable sample text
// - Grid of weight variants
// - Toggle italic if available
```

---

## Implementation Phases

### Phase 1: Core — Plugin Remote Sources

1. Add `sources` field to plugin schema
2. Validate sources on plugin load
3. Add source validation to REST executor
4. Reject unauthorized fetches with clear error

### Phase 2: Entities

1. Add `icon.yaml` to entities
2. Add `font.yaml` to entities
3. Validate entity schemas

### Phase 3: Plugins

1. Create `iconify` plugin
2. Create `google-fonts` plugin
3. Test API calls work through source validation

### Phase 4: Apps

1. Create `icons` app with browse/detail views
2. Create `fonts` app with browse/detail views
3. Build UI components (icon-card, font-specimen, etc.)

### Phase 5: Polish

1. Add copy-to-clipboard for SVG
2. Add download functionality
3. Add keyboard navigation (arrow keys in grid)
4. Cache API responses locally

---

## Open Questions

1. **Icon set metadata** — Should we pre-cache the list of icon sets, or fetch dynamically? Iconify has 150+ sets, listing them all on every load is wasteful.

2. **Font loading** — How do we load fonts for preview? Options:
   - Inject `<link>` to Google Fonts CSS
   - Download and cache font files locally
   - Use font-display: swap to avoid FOUT

3. **Download location** — Where do downloaded assets go?
   - `~/.agentos/downloads/icons/`
   - `~/.agentos/downloads/fonts/`
   - Or prompt user for location?

4. **Favorites** — Should we support favoriting icons/fonts for quick access? Would need local storage.

---

## See Also

- [`ui-capabilities.md`](../todo/ui-capabilities.md) — How apps display activities
- [`handlers.md`](../todo/handlers.md) — Plugin operation execution
- Plugin security model (TBD)
