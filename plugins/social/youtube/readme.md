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
