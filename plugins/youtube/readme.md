---
id: youtube
name: YouTube
description: Get video metadata and transcripts using yt-dlp
icon: icon.png
color: "#FF0000"
website: https://youtube.com
tags: [media, video]

requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y

# URL patterns this plugin handles
handles:
  urls:
    - "youtube.com/*"
    - "youtu.be/*"
    - "music.youtube.com/*"

# External sources this plugin needs (for CSP)
sources:
  images:
    - "https://i.ytimg.com/*"      # Video thumbnails
    - "https://yt3.ggpht.com/*"    # Channel avatars

adapters:
  video:
    terminology: Video
    mapping:
      title: .title
      description: .description
      duration_ms: ".duration | multiply:1000"
      thumbnail: .thumbnail
      creator_name: .channel
      creator_url: .channel_url
      source_id: .id
      source_url: .webpage_url
      published_at: .upload_date
      resolution: .resolution

operations:
  video.get:
    description: Get video metadata (title, creator, thumbnail, duration)
    returns: video
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
    command:
      binary: yt-dlp
      args:
        - "--dump-json"
        - "--skip-download"
        - "{{params.url}}"
      timeout: 30

  video.transcript:
    description: Get video transcript from auto-generated captions
    returns: video
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
      lang:
        type: string
        default: en
        description: Language code (e.g., en, es, fr)
    command:
      binary: bash
      args:
        - "-c"
        - |
          set -e
          TMPDIR=$(mktemp -d)
          trap "rm -rf $TMPDIR" EXIT
          
          # Download auto-generated subtitles
          yt-dlp --skip-download --write-auto-subs --sub-langs "{{params.lang}}" --convert-subs srt -o "$TMPDIR/sub_%(id)s" "{{params.url}}" >/dev/null 2>&1
          
          # Find the subtitle file
          SRTFILE=$(ls "$TMPDIR"/sub_*.srt 2>/dev/null | head -1)
          
          if [ -z "$SRTFILE" ]; then
            echo '{"error": "No auto-generated captions available for this video"}'
            exit 0
          fi
          
          # Extract clean text: remove timestamps, line numbers, empty lines, dedupe
          TRANSCRIPT=$(cat "$SRTFILE" | grep -v '^[0-9]*$' | grep -v '^[0-9][0-9]:[0-9][0-9]:[0-9][0-9]' | grep -v '^$' | awk '!seen[$0]++' | tr '\n' ' ' | sed 's/  */ /g' | sed 's/"/\\"/g')
          
          # Get full video metadata (same fields as video.get)
          METADATA=$(yt-dlp --dump-json --skip-download "{{params.url}}" 2>/dev/null)
          
          # Output JSON with all video fields plus transcript
          # The adapter will map these to video entity properties
          echo "$METADATA" | jq --arg transcript "$TRANSCRIPT" '{
            title: .title,
            description: $transcript,
            duration: .duration,
            thumbnail: .thumbnail,
            channel: .channel,
            channel_url: .channel_url,
            id: .id,
            webpage_url: .webpage_url,
            upload_date: .upload_date,
            resolution: .resolution
          }'
      timeout: 60
---

# YouTube

YouTube plugin for video metadata. Uses `yt-dlp` for all operations.

## Requirements

Install yt-dlp:

```bash
brew install yt-dlp    # macOS
apt install yt-dlp     # Linux
choco install yt-dlp   # Windows
```

## Operations

| Operation | Description |
|-----------|-------------|
| `video.get` | Get video metadata (title, creator, thumbnail, duration) |
| `video.transcript` | Get video transcript from auto-generated captions |

## URL Formats

All these formats work:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/watch?v=VIDEO_ID&t=60`
- `https://music.youtube.com/watch?v=VIDEO_ID`

## Example Response

```json
{
  "title": "Video Title",
  "description": "Video description...",
  "duration_ms": 360000,
  "thumbnail": "https://i.ytimg.com/vi/...",
  "creator_name": "Channel Name",
  "creator_url": "https://youtube.com/channel/...",
  "source_id": "dQw4w9WgXcQ",
  "source_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "resolution": "1920x1080",
  "published_at": "20210101"
}
```
