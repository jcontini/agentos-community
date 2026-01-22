---
id: youtube
name: YouTube
description: Get video transcripts, metadata, and downloads using yt-dlp
icon: icon.svg
color: "#FF0000"
website: https://youtube.com
tags: [media, video, youtube]

requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y

# Action implementations (merged from mapping.yaml)
actions:
  metadata:
    operation: read
    label: Get video info
    command:
      binary: yt-dlp
      args:
        - "--dump-json"
        - "--skip-download"
        - "{{params.url}}"
      timeout: 30
    response:
      mapping:
        id: "{{id}}"
        title: "{{title}}"
        creator: "{{channel}}"
        description: "{{description}}"
        duration: "{{duration}}"
        url: "{{webpage_url}}"
        thumbnail: "{{thumbnail}}"
        view_count: "{{view_count}}"
        upload_date: "{{upload_date}}"
        type: video

  transcribe:
    operation: read
    label: Get transcript
    command:
      binary: yt-dlp
      args:
        - "--skip-download"
        - "--write-auto-sub"
        - "--sub-lang"
        - "{{params.lang}}"
        - "--convert-subs"
        - "srt"
        - "--print"
        - "requested_subtitles"
        - "-o"
        - "-"
        - "{{params.url}}"
      timeout: 120

  download:
    operation: create
    label: Download video
    command:
      binary: yt-dlp
      args:
        - "-f"
        - "best[height<={{params.quality}}]/best"
        - "-o"
        - "~/Downloads/%(title)s.%(ext)s"
        - "--print"
        - "after_move:filepath"
        - "{{params.url}}"
      timeout: 600
    response:
      mapping:
        path: "{{output}}"

  audio:
    operation: create
    label: Extract audio (mp3)
    command:
      binary: yt-dlp
      args:
        - "-x"
        - "--audio-format"
        - "mp3"
        - "-o"
        - "~/Downloads/%(title)s.%(ext)s"
        - "--print"
        - "after_move:filepath"
        - "{{params.url}}"
      timeout: 600
    response:
      mapping:
        path: "{{output}}"
---

# YouTube

YouTube connector for the Media tool. Uses `yt-dlp` for all operations.

## Requirements

Install yt-dlp:

```bash
brew install yt-dlp
```

## Capabilities

| Action | Status | Notes |
|--------|--------|-------|
| metadata | ✅ | Full video info as JSON |
| transcribe | ✅ | Auto-generated subtitles |
| download | ✅ | Best quality up to limit |
| audio | ✅ | MP3 extraction |

## URL Formats

All these formats work:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/watch?v=VIDEO_ID&t=60`
