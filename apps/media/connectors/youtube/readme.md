---
id: youtube
name: YouTube
description: Get video transcripts, metadata, and downloads using yt-dlp
icon: icon.svg
color: "#FF0000"
website: https://youtube.com

requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y
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
