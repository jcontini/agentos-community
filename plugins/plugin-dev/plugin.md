---
id: plugin-dev
name: Plugin Development
description: Guide for building, auditing, and updating AgentOS plugins
category: code
icon: material-symbols:build
color: "#10B981"

auth:
  type: local

requires:
  - yq

actions:
  audit:
    readonly: true
    description: Audit a plugin for common issues and best practices
    params:
      path:
        type: string
        required: true
        description: Path to the plugin.md file to audit
    run: |
      require_file "$PARAM_PATH"
      
      echo "# Plugin Audit: $PARAM_PATH"
      echo ""
      
      # Extract frontmatter to temp file for yq
      TMPYAML=$(mktemp)
      trap "rm -f $TMPYAML" EXIT
      sed -n '/^---$/,/^---$/p' "$PARAM_PATH" | sed '1d;$d' > "$TMPYAML"
      
      # Check required fields
      echo "## Required Fields"
      for field in id name description category; do
        VAL=$(yq ".$field" "$TMPYAML" | grep -v '^null$')
        if [ -n "$VAL" ]; then
          echo "✅ $field: $VAL"
        else
          echo "❌ $field: MISSING"
        fi
      done
      echo ""
      
      # Check icon format
      echo "## Icon"
      ICON=$(yq '.icon' "$TMPYAML" | grep -v '^null$')
      if [ -n "$ICON" ]; then
        if echo "$ICON" | grep -q ":"; then
          echo "✅ Iconify format: $ICON"
        elif echo "$ICON" | grep -q "^http"; then
          echo "✅ URL format: $ICON"
        else
          echo "⚠️  Unknown icon format: $ICON"
        fi
      else
        echo "⚠️  No icon defined"
      fi
      echo ""
      
      # Check for forbidden patterns
      echo "## Error Handling"
      FOUND_ISSUES=0
      if grep -q '2>/dev/null' "$PARAM_PATH"; then
        echo "❌ Found '2>/dev/null' - hides errors from activity log"
        FOUND_ISSUES=1
      fi
      if grep -q '2>&-' "$PARAM_PATH"; then
        echo "❌ Found '2>&-' - closes stderr"
        FOUND_ISSUES=1
      fi
      if grep -q '&>/dev/null' "$PARAM_PATH"; then
        echo "❌ Found '&>/dev/null' - hides all output"
        FOUND_ISSUES=1
      fi
      if [ $FOUND_ISSUES -eq 0 ]; then
        echo "✅ No forbidden error suppression patterns"
      fi
      echo ""
      
      # Check for helpers usage
      echo "## Helpers"
      HELPERS=$(yq '.helpers' "$TMPYAML" | grep -v '^null$')
      if [ -n "$HELPERS" ]; then
        echo "✅ Uses helpers block for shared logic"
      else
        ACTIONS=$(yq '.actions | keys | length' "$TMPYAML")
        if [ "$ACTIONS" -gt 1 ]; then
          echo "⚠️  Multiple actions ($ACTIONS) but no helpers block"
        else
          echo "ℹ️  No helpers block (may not need one)"
        fi
      fi
      echo ""
      
      # Check actions have descriptions
      echo "## Actions"
      yq '.actions | keys | .[]' "$TMPYAML" | while read -r action; do
        DESC=$(yq ".actions.$action.description" "$TMPYAML" | grep -v '^null$')
        if [ -n "$DESC" ]; then
          echo "✅ $action: $DESC"
        else
          echo "❌ $action: missing description"
        fi
      done
      echo ""
      
      echo "✅ Audit complete"
---

# Plugin Development Guide

Use this guide when building, auditing, or updating AgentOS plugins.

## Plugin Structure

Plugins live in `plugins/{id}/plugin.md` with YAML frontmatter + markdown body.

```yaml
---
id: my-plugin
name: My Plugin
description: What it does (one line)
category: productivity  # productivity, communication, search, code, finance, media
icon: material-symbols:icon-name  # Iconify format OR URL
color: "#hexcolor"

# Authentication (pick one)
auth:
  type: local  # No credentials needed

# OR
auth:
  type: api_key
  header: Authorization  # or X-Api-Key, etc.
  prefix: "Bearer "      # prefix before key
  help_url: https://...  # where to get the key

# Dependencies
requires:
  - curl  # Simple: binary name
  - name: yt-dlp  # Structured: with install commands
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp

# Shared functions (available to all actions)
helpers: |
  my_helper() {
    echo "reusable logic"
  }

# User-configurable settings
settings:
  num_results:
    label: Number of Results
    type: integer
    default: "5"
    min: 1
    max: 100
  mode:
    label: Mode
    type: enum
    default: "auto"
    options: [auto, fast, thorough]

actions:
  my_action:
    description: What this action does
    params:
      query:
        type: string
        required: true
        description: What this param is for
      limit:
        type: integer
        default: "10"
    run: |
      echo "Query: $PARAM_QUERY, Limit: $PARAM_LIMIT"
---

# My Plugin

Instructions for AI go here...
```

## Environment Variables

These are auto-injected into every `run:` script:

| Variable | Description |
|----------|-------------|
| `PARAM_{NAME}` | Each param value (uppercased) |
| `PARAM_ACTION` | The action being called |
| `PLUGIN_DIR` | Path to plugin folder (for scripts/) |
| `AUTH_TOKEN` | Credential if auth configured |
| `SETTING_{NAME}` | Plugin settings (uppercased) |
| `AGENTOS_DOWNLOADS` | User's downloads folder |
| `AGENTOS_CACHE` | Cache directory |
| `AGENTOS_DATA` | Data directory |

## Built-in Helper Functions

Available in all `run:` scripts:

```bash
error "message"      # Print to stderr and exit 1
warn "message"       # Print warning to stderr
downloads            # Echo the downloads path
require_file "path"  # Error if file doesn't exist
require_dir "path"   # Error if dir doesn't exist
```

## The `helpers:` Block

Define shared functions used by multiple actions:

```yaml
helpers: |
  ensure_deps() {
    command -v jq || error "jq required"
  }
  
  call_api() {
    curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$1"
  }

actions:
  list:
    run: |
      ensure_deps
      call_api "https://api.example.com/items" | jq .
  
  get:
    run: |
      ensure_deps
      call_api "https://api.example.com/items/$PARAM_ID" | jq .
```

## Plugins with Scripts

For complex logic, use a `scripts/` folder:

```
plugins/
  browser/
    plugin.md
    scripts/
      browser.mjs   # Node.js, Python, etc.
```

Reference via `$PLUGIN_DIR`:

```yaml
helpers: |
  browser() {
    node "$PLUGIN_DIR/scripts/browser.mjs"
  }

actions:
  click:
    run: browser
```

## Icons

Two formats supported:

1. **Iconify** (preferred): `icon: material-symbols:web`
2. **URL**: `icon: https://cdn.simpleicons.org/todoist`

Browse icons: https://icon-sets.iconify.design/

## Categories

| Category | Use for |
|----------|---------|
| `productivity` | Tasks, notes, bookmarks |
| `communication` | Email, messaging |
| `search` | Web search, extraction |
| `code` | GitHub, dev tools |
| `finance` | Banking, payments |
| `media` | Video, audio, images |

Unknown categories automatically map to "Other".

## Best Practices

### Do ✅

- Use `helpers:` for shared logic
- Use `error()` for failures (visible in activity log)
- Keep `run:` blocks simple (call helpers)
- Use `$PLUGIN_DIR` for scripts, not hardcoded paths
- Return JSON for structured data

### Don't ❌

- Suppress stderr (`2>/dev/null` hides errors)
- Use complex inline scripts (use helpers or scripts/)
- Hardcode paths (use env vars)
- Ignore exit codes

## Param Types

| Type | Description |
|------|-------------|
| `string` | Text input |
| `integer` | Number |
| `boolean` | true/false |

## Settings Types

| Type | Description |
|------|-------------|
| `string` | Text input |
| `integer` | Number with optional `min`/`max` |
| `boolean` | Toggle (default as `"true"` or `"false"` string) |
| `enum` | Dropdown with `options` array |

## macOS Permissions

For plugins accessing protected resources:

```yaml
permissions:
  - full_disk_access   # Messages, Mail, Safari DBs
  - contacts           # Contacts database
  - calendar           # Calendar/Reminders
  - automation:Finder  # AppleScript control
```

## Testing Locally

1. Fork the plugins repo
2. In AgentOS Settings → Developer, set plugins source to your local path
3. Changes hot-reload automatically

## Auditing Plugins

When reviewing a plugin, check:

1. **Structure**: Valid YAML, required fields present
2. **Errors**: No stderr suppression, uses `error()` helper
3. **Helpers**: Shared logic extracted to `helpers:` block
4. **Paths**: Uses `$PLUGIN_DIR`, `$AGENTOS_DOWNLOADS`, not hardcoded
5. **Params**: All required params have descriptions
6. **Docs**: Markdown body explains usage clearly


## Cursor MCP Connection Issues

During plugin development, Cursor's MCP connection can get stuck or disabled. To fix:

```bash
# Toggle the MCP config to force reconnect (MUST wait 1 second between renames)
mv ~/.cursor/mcp.json ~/.cursor/mcp.json.tmp
sleep 1
mv ~/.cursor/mcp.json.tmp ~/.cursor/mcp.json
```

This renames the config and back, triggering Cursor to re-read and reconnect. Do this whenever you get "Not connected" errors from AgentOS tools.

## Contributing Plugins

To contribute a plugin to the public repo:

1. Fork the [AgentOS-Plugins](https://github.com/jcontini/AgentOS-Plugins) repo
2. Create your plugin in `plugins/{id}/plugin.md`
3. Run the audit tool to check for issues:
   ```
   UsePlugin(plugin: "plugin-dev", tool: "audit", params: {path: "plugins/my-plugin/plugin.md"})
   ```
4. Test locally by setting your fork as the plugins source in AgentOS Settings
5. Submit a PR

The audit tool checks for common issues before you submit.
