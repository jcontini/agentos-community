---
id: youtube
name: YouTube
description: Get video transcripts and download videos using yt-dlp
category: media
icon: https://cdn.simpleicons.org/youtube
color: "#FF0000"
protocol: shell

requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y

actions:
  transcribe:
    description: Get transcript text from a YouTube video
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
      lang:
        type: string
        default: en
        description: Subtitle language code (e.g., en, es, fr)
    run: |
      TMPDIR=$(mktemp -d)
      trap "rm -rf $TMPDIR" EXIT
      yt-dlp --skip-download --write-auto-sub --sub-lang "$PARAM_LANG" \
        --convert-subs srt "$PARAM_URL" -o "$TMPDIR/video" 2>/dev/null
      if ls "$TMPDIR"/*.srt 1>/dev/null 2>&1; then
        cat "$TMPDIR"/*.srt | \
          grep -v "^[0-9]*$" | \
          grep -v -- "-->" | \
          grep -v "^\s*$" | \
          sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
          uniq
      else
        error "No subtitles available for this video"
      fi

  metadata:
    description: Get video metadata as JSON (title, duration, channel, etc)
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
    run: yt-dlp --dump-json --skip-download "$PARAM_URL"

  download:
    description: Download video file to your Downloads folder
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
      quality:
        type: string
        default: "1080"
        description: Maximum video height (e.g., 720, 1080, 1440, 2160)
    run: |
      OUTPUT_DIR="$(downloads)"
      yt-dlp -f "best[height<=$PARAM_QUALITY]/best" \
        -o "$OUTPUT_DIR/%(title)s.%(ext)s" "$PARAM_URL"
      echo "Downloaded to: $OUTPUT_DIR/"

  audio:
    description: Extract audio as MP3 to your Downloads folder
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
    run: |
      OUTPUT_DIR="$(downloads)"
      yt-dlp -x --audio-format mp3 \
        -o "$OUTPUT_DIR/%(title)s.%(ext)s" "$PARAM_URL"
      echo "Downloaded to: $OUTPUT_DIR/"
---

# YouTube

Extract transcripts, download videos, and get metadata from YouTube using yt-dlp.

## Requirements

This plugin requires `yt-dlp` to be installed on your system:

```bash
# macOS (Homebrew)
brew install yt-dlp

# Python (pip)
pip install yt-dlp

# Check installation
which yt-dlp
```

## Tools

### transcribe
Get the transcript/subtitles from a YouTube video as plain text.

**Parameters:**
- `url` (required): YouTube video URL
- `lang` (optional): Subtitle language code, default "en"

**Example:**
```
use-plugin(plugin: "youtube", tool: "transcribe", params: {url: "https://youtube.com/watch?v=..."})
```

**Notes:**
- Uses auto-generated captions if available
- Returns cleaned text without timestamps
- Returns error if no subtitles available

### metadata
Get video metadata as JSON (title, duration, channel, view count, etc).

**Parameters:**
- `url` (required): YouTube video URL

**Example:**
```
use-plugin(plugin: "youtube", tool: "metadata", params: {url: "https://youtube.com/watch?v=..."})
```

### download
Download the video file to the user's Downloads folder.

**Parameters:**
- `url` (required): YouTube video URL
- `quality` (optional): Max video height, default "1080"

**Example:**
```
use-plugin(plugin: "youtube", tool: "download", params: {url: "https://youtube.com/watch?v=...", quality: "720"})
```

### audio
Extract audio as MP3 to the user's Downloads folder.

**Parameters:**
- `url` (required): YouTube video URL

**Example:**
```
use-plugin(plugin: "youtube", tool: "audio", params: {url: "https://youtube.com/watch?v=..."})
```

## URL Formats

All these formats work:
- Full URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- Short URL: `https://youtu.be/dQw4w9WgXcQ`
- With timestamp: `https://youtube.com/watch?v=dQw4w9WgXcQ&t=60`

## Tips

- **Transcripts**: Great for summarizing videos, extracting quotes, or making content searchable
- **Metadata**: Check video length before downloading, get channel info
- **Quality**: Use lower quality (720, 480) for faster downloads or to save space
- **Audio**: Perfect for podcasts, music, or when you only need the audio track
