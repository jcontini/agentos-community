---
id: computer
name: Computer
description: Open apps, URLs, and save files on your Mac
category: productivity
icon: https://cdn.simpleicons.org/apple
color: "#000000"
protocol: shell

actions:
  open-app:
    description: Open an application by name
    params:
      name:
        type: string
        required: true
        description: App name (e.g., Safari, Slack, Finder, "Google Chrome")
    run: open -a "$PARAM_NAME"

  open-url:
    description: Open a URL in a browser
    params:
      url:
        type: string
        required: true
        description: URL to open (https://, maps://, mailto:, etc.)
      app:
        type: string
        description: App to open URL with (e.g., Safari, "Google Chrome"). Uses system default if not specified.
    run: |
      if [ -n "$PARAM_APP" ]; then
        open -a "$PARAM_APP" "$PARAM_URL"
      else
        open "$PARAM_URL"
      fi

  save-file:
    description: Save content to Downloads folder and optionally open it
    params:
      filename:
        type: string
        required: true
        description: Filename with extension (e.g., report.html, data.json)
      content:
        type: string
        required: true
        description: Content to save to the file
      open:
        type: boolean
        default: "true"
        description: Open the file after saving
    run: |
      OUTPUT_DIR="${AGENTOS_DOWNLOADS:-$HOME/Downloads}"
      printf '%s' "$PARAM_CONTENT" > "$OUTPUT_DIR/$PARAM_FILENAME"
      [ "$PARAM_OPEN" = "true" ] && open "$OUTPUT_DIR/$PARAM_FILENAME"
      echo "Saved to: $OUTPUT_DIR/$PARAM_FILENAME"

  reveal-file:
    description: Reveal a file or folder in Finder
    params:
      path:
        type: string
        required: true
        description: Path to reveal (e.g., ~/Downloads, /Applications)
    run: open -R "$PARAM_PATH"
---

# Computer

Control your Mac through agentOS. Open apps, URLs, and save files.

## Actions

### open-app
Open any application by name.

```
action: open-app
params: {name: "Safari"}
```

```
action: open-app
params: {name: "Google Chrome"}
```

```
action: open-app
params: {name: "Slack"}
```

### open-url
Open a URL. Uses your system default browser.

**Web URLs:**
```
action: open-url
params: {url: "https://google.com"}
```

**Apple Maps directions:**
```
action: open-url
params: {url: "maps://?daddr=SFO+Airport"}
```

With start and end:
```
action: open-url
params: {url: "maps://?saddr=San+Francisco&daddr=Los+Angeles"}
```

**Google Maps directions** (opens in browser):
```
action: open-url
params: {url: "https://www.google.com/maps/dir/San+Francisco/Los+Angeles"}
```

**Email:**
```
action: open-url
params: {url: "mailto:hello@example.com?subject=Hello"}
```

### save-file
Save content to Downloads folder.

```
action: save-file
params: {filename: "report.html", content: "<html><body>Hello</body></html>"}
```

Save without opening:
```
action: save-file
params: {filename: "data.json", content: "{\"key\": \"value\"}", open: false}
```

### reveal-file
Show a file or folder in Finder.

```
action: reveal-file
params: {path: "~/Downloads"}
```

## URL Schemes

| Scheme | Opens |
|--------|-------|
| `https://...` | Default browser |
| `maps://...` | Apple Maps |
| `mailto:...` | Default email app |
| `tel:...` | Phone/FaceTime |
| `facetime:...` | FaceTime |
| `music://...` | Apple Music |
| `shortcuts://...` | Shortcuts app |

## Tips

- **Maps preference**: Ask the user "Apple Maps or Google Maps?" and use the appropriate URL
- **App names with spaces**: Quote them in params, e.g., `"Google Chrome"`
- **System defaults**: URLs automatically open in the user's default browser (set in System Settings)

