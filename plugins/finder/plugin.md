---
id: finder
name: Finder
description: Open apps, URLs, files, and navigate your Mac file system
category: productivity
icon: https://upload.wikimedia.org/wikipedia/commons/b/b9/Finder_Icon_macOS_Tahoe.png
color: "#1C8BF4"
protocol: shell
platform: macos
requires:
  - name: tree
    install:
      macos: brew install tree
      linux: sudo apt install -y tree
      windows: choco install tree -y

helpers: |
  # Finder-specific helpers
  is_url() { [[ "$1" == http* ]] || [[ "$1" == maps://* ]]; }
  is_app() { [ -d "/Applications/$1.app" ] || [[ "$1" == *.app ]]; }

actions:
  open:
    description: Open an app, URL, or file
    params:
      target:
        type: string
        required: true
        description: App name (e.g., "Safari"), URL, or file path
      with:
        type: string
        description: Open with a specific app (optional)
    run: |
      if [ -n "$PARAM_WITH" ]; then
        open -a "$PARAM_WITH" "$PARAM_TARGET"
      elif is_url "$PARAM_TARGET"; then
        open "$PARAM_TARGET"
      elif is_app "$PARAM_TARGET"; then
        open -a "$PARAM_TARGET"
      else
        require_path "$PARAM_TARGET"
        open "$PARAM_TARGET"
      fi

  browse:
    description: List directory contents or show tree structure
    params:
      path:
        type: string
        default: "."
        description: Directory path
      tree:
        type: boolean
        default: "false"
        description: Show recursive tree view instead of flat list
      depth:
        type: number
        description: Tree depth limit (only with tree=true)
    run: |
      require_dir "$PARAM_PATH"
      if [ "$PARAM_TREE" = "true" ]; then
        [ -n "$PARAM_DEPTH" ] && tree -L "$PARAM_DEPTH" "$PARAM_PATH" || tree "$PARAM_PATH"
      else
        ls -lah "$PARAM_PATH"
      fi

  read:
    description: Read file info and/or contents
    params:
      path:
        type: string
        required: true
        description: File or directory path
      info-only:
        type: boolean
        default: "false"
        description: Only show metadata, skip file contents
    run: |
      require_path "$PARAM_PATH"
      
      # Determine type
      if [ -d "$PARAM_PATH" ]; then
        TYPE="directory"
      elif [ -f "$PARAM_PATH" ]; then
        TYPE="file"
      else
        TYPE="other"
      fi
      
      # Get metadata
      MIME=$(file -b --mime-type "$PARAM_PATH" 2>/dev/null || echo "unknown")
      SIZE=$(stat -f%z "$PARAM_PATH" 2>/dev/null || stat -c%s "$PARAM_PATH" 2>/dev/null || echo "0")
      EXT="${PARAM_PATH##*.}"
      [ "$EXT" = "$PARAM_PATH" ] && EXT=""
      
      echo "Type: $TYPE"
      echo "MIME: $MIME"
      echo "Size: $SIZE bytes"
      [ -n "$EXT" ] && echo "Extension: $EXT"
      echo "Path: $PARAM_PATH"
      
      # Show contents for text files (unless info-only)
      if [ "$PARAM_INFO_ONLY" != "true" ] && [ "$TYPE" = "file" ]; then
        case "$MIME" in
          text/*|application/json|application/javascript|application/xml|application/x-sh|application/x-shellscript)
            echo ""
            echo "--- Contents ---"
            cat "$PARAM_PATH"
            ;;
          application/octet-stream)
            # Check extension for common text files
            case "$EXT" in
              md|txt|js|ts|jsx|tsx|py|rb|go|rs|sh|bash|zsh|yaml|yml|toml|ini|cfg|conf|html|css|scss|less|sql|graphql|vue|svelte)
                echo ""
                echo "--- Contents ---"
                cat "$PARAM_PATH"
                ;;
              *)
                echo ""
                echo "(Binary file - use 'open' to view)"
                ;;
            esac
            ;;
          *)
            echo ""
            echo "(Binary file - use 'open' to view)"
            ;;
        esac
      fi

  file:
    description: Filesystem operations - create dir, write file, move, copy, rename, or delete
    params:
      op:
        type: string
        required: true
        description: "Operation: create, write, move, copy, rename, or delete"
      path:
        type: string
        required: true
        description: Path to operate on (relative paths default to Downloads for write)
      content:
        type: string
        description: File content (for write)
      to:
        type: string
        description: Destination path or new name (for move/copy/rename)
      recursive:
        type: boolean
        default: "false"
        description: Required for copy/delete of directories
      open:
        type: boolean
        default: "false"
        description: Open file after writing (for write)
    run: |
      # For write with relative path, default to Downloads
      DOWNLOADS="$(downloads)"
      
      case "$PARAM_OP" in
        create)
          if [ -e "$PARAM_PATH" ]; then
            [ -d "$PARAM_PATH" ] && echo "Already exists: $PARAM_PATH" && exit 0
            error "Path exists but is not a directory: $PARAM_PATH"
          fi
          mkdir -p "$PARAM_PATH"
          echo "Created: $PARAM_PATH"
          ;;
        
        write)
          # Determine target path (relative = Downloads, absolute = as-is)
          if [[ "$PARAM_PATH" == /* ]]; then
            TARGET="$PARAM_PATH"
          else
            TARGET="$DOWNLOADS/$PARAM_PATH"
          fi
          # Create parent directories if needed
          mkdir -p "$(dirname "$TARGET")"
          # Write content
          printf '%s' "$PARAM_CONTENT" > "$TARGET"
          echo "Saved: $TARGET"
          # Optionally open
          [ "$PARAM_OPEN" = "true" ] && open "$TARGET"
          ;;
        
        move)
          require_path "$PARAM_PATH"
          # If destination is a directory, move into it
          if [ -d "$PARAM_TO" ]; then
            DEST="$PARAM_TO/$(basename "$PARAM_PATH")"
          else
            DEST="$PARAM_TO"
          fi
          [ -e "$DEST" ] && [ "$PARAM_PATH" != "$DEST" ] && error "Destination exists: $DEST"
          mv "$PARAM_PATH" "$DEST"
          echo "Moved to: $DEST"
          ;;
        
        copy)
          require_path "$PARAM_PATH"
          # If destination is a directory, copy into it
          if [ -d "$PARAM_TO" ]; then
            DEST="$PARAM_TO/$(basename "$PARAM_PATH")"
          else
            DEST="$PARAM_TO"
          fi
          [ -e "$DEST" ] && error "Destination exists: $DEST"
          if [ -d "$PARAM_PATH" ]; then
            [ "$PARAM_RECURSIVE" != "true" ] && error "Use recursive=true for directories"
            cp -r "$PARAM_PATH" "$DEST"
          else
            cp "$PARAM_PATH" "$DEST"
          fi
          echo "Copied to: $DEST"
          ;;
        
        rename)
          require_path "$PARAM_PATH"
          DIR=$(dirname "$PARAM_PATH")
          NEW_PATH="$DIR/$PARAM_TO"
          [ -e "$NEW_PATH" ] && error "Destination exists: $NEW_PATH"
          mv "$PARAM_PATH" "$NEW_PATH"
          echo "Renamed to: $NEW_PATH"
          ;;
        
        delete)
          require_path "$PARAM_PATH"
          if [ -d "$PARAM_PATH" ]; then
            [ "$PARAM_RECURSIVE" != "true" ] && error "Use recursive=true for directories"
            rm -rf "$PARAM_PATH"
          else
            rm "$PARAM_PATH"
          fi
          echo "Deleted: $PARAM_PATH"
          ;;
        
        *)
          error "Unknown op '$PARAM_OP'. Use: create, move, copy, rename, delete"
          ;;
      esac

  edit:
    description: Edit a file - replace lines, insert, find-replace, or append
    params:
      op:
        type: string
        required: true
        description: "Operation: replace, insert, find-replace, or append"
      path:
        type: string
        required: true
        description: File path to edit
      content:
        type: string
        required: true
        description: Content to insert/replace/append
      line:
        type: number
        description: Line number for insert (1-based)
      start:
        type: number
        description: Start line for replace (1-based)
      end:
        type: number
        description: End line for replace (1-based, inclusive)
      find:
        type: string
        description: Text to find (for find-replace)
      global:
        type: boolean
        default: "true"
        description: Replace all occurrences (for find-replace)
    run: |
      require_file "$PARAM_PATH"
      [ ! -w "$PARAM_PATH" ] && error "File not writable: $PARAM_PATH"
      
      TOTAL_LINES=$(wc -l < "$PARAM_PATH" | tr -d ' ')
      
      case "$PARAM_OP" in
        replace)
          # Replace lines start-end with content
          [ -z "$PARAM_START" ] && error "'start' required for replace"
          [ -z "$PARAM_END" ] && error "'end' required for replace"
          [ "$PARAM_START" -lt 1 ] || [ "$PARAM_START" -gt "$TOTAL_LINES" ] && \
            error "start=$PARAM_START out of range (1-$TOTAL_LINES)"
          [ "$PARAM_END" -lt "$PARAM_START" ] || [ "$PARAM_END" -gt "$TOTAL_LINES" ] && \
            error "end=$PARAM_END out of range"
          
          TEMP=$(mktemp)
          [ "$PARAM_START" -gt 1 ] && sed -n "1,$((PARAM_START - 1))p" "$PARAM_PATH" > "$TEMP"
          printf '%s\n' "$PARAM_CONTENT" >> "$TEMP"
          [ "$PARAM_END" -lt "$TOTAL_LINES" ] && sed -n "$((PARAM_END + 1)),${TOTAL_LINES}p" "$PARAM_PATH" >> "$TEMP"
          mv "$TEMP" "$PARAM_PATH"
          echo "Replaced lines $PARAM_START-$PARAM_END"
          ;;
        
        insert)
          # Insert content at line (shifts existing lines down)
          [ -z "$PARAM_LINE" ] && error "'line' required for insert"
          [ "$PARAM_LINE" -lt 1 ] || [ "$PARAM_LINE" -gt $((TOTAL_LINES + 1)) ] && \
            error "line=$PARAM_LINE out of range (1-$((TOTAL_LINES + 1)))"
          
          TEMP=$(mktemp)
          [ "$PARAM_LINE" -gt 1 ] && sed -n "1,$((PARAM_LINE - 1))p" "$PARAM_PATH" > "$TEMP"
          printf '%s\n' "$PARAM_CONTENT" >> "$TEMP"
          [ "$PARAM_LINE" -le "$TOTAL_LINES" ] && sed -n "${PARAM_LINE},${TOTAL_LINES}p" "$PARAM_PATH" >> "$TEMP"
          mv "$TEMP" "$PARAM_PATH"
          echo "Inserted at line $PARAM_LINE"
          ;;
        
        find-replace)
          # Find and replace text
          [ -z "$PARAM_FIND" ] && error "'find' required for find-replace"
          
          # Escape special characters
          SEARCH=$(printf '%s\n' "$PARAM_FIND" | sed 's/[[\.*^$()+?{|]/\\&/g')
          REPLACE=$(printf '%s\n' "$PARAM_CONTENT" | sed 's/\\/\\\\/g' | sed 's/&/\\&/g' | sed 's/\//\\\//g')
          
          if [ "$PARAM_GLOBAL" = "true" ]; then
            sed -i '' "s/$SEARCH/$REPLACE/g" "$PARAM_PATH"
          else
            sed -i '' "s/$SEARCH/$REPLACE/" "$PARAM_PATH"
          fi
          echo "Replaced text"
          ;;
        
        append)
          # Append content to end of file
          printf '\n%s\n' "$PARAM_CONTENT" >> "$PARAM_PATH"
          echo "Appended to file"
          ;;
        
        *)
          error "Unknown op '$PARAM_OP'. Use: replace, insert, find-replace, append"
          ;;
      esac

---

# Finder

Control your Mac - open anything, browse directories, read files, and full filesystem operations.

## Tools (5 total)

| Action | Purpose |
|--------|---------|
| `open` | Open apps, URLs, or files |
| `browse` | List or tree directories |
| `read` | Get file info and contents |
| `file` | Create, write, move, copy, rename, delete |
| `edit` | Replace lines, insert, find-replace, append |

### open
Open an app, URL, or file. Automatically detects the type.

**Open an app:**
```
action: open
params: {target: "Safari"}
```

**Open a URL:**
```
action: open
params: {target: "https://google.com"}
```

**Open a file:**
```
action: open
params: {target: "/Users/joe/Documents/report.pdf"}
```

**Open a file with a specific app:**
```
action: open
params: {target: "document.md", with: "Typora"}
```

**Open Maps directions:**
```
action: open
params: {target: "maps://?daddr=SFO+Airport"}
```

### browse
List directory contents or show a tree view.

**List directory:**
```
action: browse
params: {path: "/Users/joe/Documents"}
```

**Tree view:**
```
action: browse
params: {path: "/Users/joe/projects", tree: true}
```

**Tree with depth limit:**
```
action: browse
params: {path: ".", tree: true, depth: 2}
```

### read
Read file metadata and contents. For text files, shows both info and contents by default.

**Read a file:**
```
action: read
params: {path: "/Users/joe/Documents/notes.md"}
```

**Info only (skip contents):**
```
action: read
params: {path: "/Users/joe/Documents/large-file.json", info-only: true}
```

Output includes: Type, MIME type, Size, Extension, and Contents (for text files).

### file
Filesystem operations for files and directories.

**Create a directory:**
```
action: file
params: {op: "create", path: "/Users/joe/new-folder"}
```

**Create nested directories:**
```
action: file
params: {op: "create", path: "/Users/joe/a/b/c"}
```

**Move a file or directory:**
```
action: file
params: {op: "move", path: "file.txt", to: "/Users/joe/Desktop/file.txt"}
```

**Copy a file:**
```
action: file
params: {op: "copy", path: "file.txt", to: "file-backup.txt"}
```

**Copy a directory (requires recursive):**
```
action: file
params: {op: "copy", path: "my-folder", to: "my-folder-backup", recursive: true}
```

**Rename a file or directory:**
```
action: file
params: {op: "rename", path: "old-name.txt", to: "new-name.txt"}
```

**Delete a file:**
```
action: file
params: {op: "delete", path: "file.txt"}
```

**Delete a directory (requires recursive):**
```
action: file
params: {op: "delete", path: "temp-folder", recursive: true}
```

**Write a file to Downloads (default for relative paths):**
```
action: file
params: {op: "write", path: "report.html", content: "<html>...</html>"}
```

**Write a file to a specific location:**
```
action: file
params: {op: "write", path: "/Users/joe/Documents/notes.md", content: "# Notes\n..."}
```

**Write and open immediately:**
```
action: file
params: {op: "write", path: "report.html", content: "<html>...</html>", open: true}
```

### edit
Edit file contents - replace lines, insert, find-replace, or append.

**Replace lines (most reliable for targeted edits):**
```
action: edit
params: {op: "replace", path: "main.js", start: 10, end: 15, content: "const x = 'new';"}
```

**Insert at a line (shifts existing lines down):**
```
action: edit
params: {op: "insert", path: "main.js", line: 5, content: "// New comment"}
```

**Find and replace text:**
```
action: edit
params: {op: "find-replace", path: "main.js", find: "oldVar", content: "newVar"}
```

**Replace only first occurrence:**
```
action: edit
params: {op: "find-replace", path: "main.js", find: "oldVar", content: "newVar", global: false}
```

**Append to end of file:**
```
action: edit
params: {op: "append", path: "main.js", content: "// End of file"}
```

## Tips

- **File paths**: Absolute paths go where specified. Relative paths in `write` default to Downloads.
- **Downloads folder**: Set in agentOS settings. AI can override with absolute paths.
- **Tree command**: Requires `tree` (`brew install tree`)
- **Reading files**: `read` auto-detects text vs binary. Binary files show "(Binary file - use 'open' to view)"
- **Editing**: Always `read` a file first to see line numbers before using `edit`
- **Line numbers**: All line operations are 1-based (first line = 1)
