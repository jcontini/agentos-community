---
id: youtube
name: YouTube
description: Get video metadata and transcripts using yt-dlp
icon: icon.png
color: "#FF0808"
website: https://youtube.com

requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y

# External sources this plugin needs (for CSP)
# Note: Specifying "ytimg.com" allows all subdomains (i.ytimg.com, i9.ytimg.com, etc.)
sources:
  images:
    - ytimg.com            # Video thumbnails (all CDN subdomains)
    - ggpht.com            # Channel avatars (yt3.ggpht.com, etc.)

adapters:
  video:
    terminology: Video
    mapping:
      id: .id
      remote_id: .id
      source_url: .webpage_url
      title: .title
      description: .description
      transcript: .transcript
      duration_ms: .duration * 1000
      thumbnail: .thumbnail
      creator.name: .channel
      creator.url: .channel_url
      published_at: .upload_date
      resolution: .resolution
      view_count: .view_count

operations:
  video.search:
    description: Search YouTube videos by query (returns 10 results sorted by relevance)
    returns: video[]
    web_url: "https://www.youtube.com/results?search_query={{params.query}}"
    params:
      query:
        type: string
        required: true
        description: Search query
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - |
          yt-dlp --flat-playlist --dump-json "ytsearch10:{{params.query}}" 2>/dev/null | jq -s '[.[] | {
            title: .title,
            description: .description,
            duration: .duration,
            thumbnail: (.thumbnails[-1].url // null),
            channel: .channel,
            channel_url: .channel_url,
            id: .id,
            webpage_url: ("https://www.youtube.com/watch?v=" + .id),
            view_count: .view_count
          }]'
      timeout: 60

  video.search_recent:
    description: Search YouTube videos by query (returns 10 results sorted by upload date, newest first)
    returns: video[]
    web_url: "https://www.youtube.com/results?search_query={{params.query}}&sp=CAI"
    params:
      query:
        type: string
        required: true
        description: Search query
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - |
          yt-dlp --flat-playlist --dump-json "ytsearchdate10:{{params.query}}" 2>/dev/null | jq -s '[.[] | {
            title: .title,
            description: .description,
            duration: .duration,
            thumbnail: (.thumbnails[-1].url // null),
            channel: .channel,
            channel_url: .channel_url,
            id: .id,
            webpage_url: ("https://www.youtube.com/watch?v=" + .id),
            view_count: .view_count
          }]'
      timeout: 60

  video.list:
    description: List the latest 20 videos from a YouTube channel or playlist
    returns: video[]
    web_url: "{{params.url}}"
    handles_urls:
      - "youtube.com/@*"
      - "youtube.com/channel/*"
      - "youtube.com/c/*"
      - "youtube.com/playlist*"
    params:
      url:
        type: string
        required: true
        description: YouTube channel URL (e.g., youtube.com/@channelname) or playlist URL
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - |
          yt-dlp --flat-playlist --dump-json --playlist-end 20 "{{params.url}}" 2>/dev/null | jq -s '[.[] | {
            title: .title,
            description: .description,
            duration: .duration,
            thumbnail: (.thumbnails[-1].url // null),
            channel: .channel,
            channel_url: .channel_url,
            id: .id,
            webpage_url: ("https://www.youtube.com/watch?v=" + .id),
            view_count: .view_count
          }]'
      timeout: 60

  video.get:
    description: Get video metadata (title, creator, thumbnail, duration)
    returns: video
    web_url: "{{params.url}}"
    handles_urls:
      - "youtube.com/*"
      - "youtu.be/*"
      - "music.youtube.com/*"
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
    web_url: "{{params.url}}"
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
        - "-l"
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
            description: .description,
            transcript: $transcript,
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

YouTube plugin for searching, browsing, and getting video metadata. Uses `yt-dlp` for all operations — no API key required.

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
| `video.search` | Search YouTube videos (sorted by relevance) |
| `video.search_recent` | Search YouTube videos (sorted by upload date, newest first) |
| `video.list` | List videos from a channel or playlist |
| `video.get` | Get full metadata for a single video |
| `video.transcript` | Get video transcript from auto-generated captions |

## video.search

Search YouTube videos sorted by relevance. Returns 10 results.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `query` | string | Search query |

**Example:**

```bash
POST /api/plugins/youtube/video.search
{"query": "rust programming tutorial"}
```

## video.search_recent

Search YouTube videos sorted by upload date (newest first). Returns 10 results. Great for finding recent content on a topic.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `query` | string | Search query |

**Example:**

```bash
POST /api/plugins/youtube/video.search_recent
{"query": "italian citizenship law 2026"}
```

## video.list

List the latest 20 videos from a YouTube channel or playlist.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `url` | string | Channel or playlist URL |

**Supported URL formats:**
- `https://www.youtube.com/@channelname`
- `https://www.youtube.com/@channelname/videos`
- `https://www.youtube.com/channel/UCxxxxxxx`
- `https://www.youtube.com/c/channelname`
- `https://www.youtube.com/playlist?list=PLxxxxxxx`

**Example:**

```bash
POST /api/plugins/youtube/video.list
{"url": "https://www.youtube.com/@channelname"}
```

## video.get

Get full metadata for a single video.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `url` | string | YouTube video URL |

**Supported URL formats:**
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://youtube.com/watch?v=VIDEO_ID&t=60`
- `https://music.youtube.com/watch?v=VIDEO_ID`

## video.transcript

Get the transcript from auto-generated captions.

**Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | YouTube video URL |
| `lang` | string | "en" | Language code (en, es, fr, etc.) |

## Response Schema

All operations return videos with these fields:

```json
{
  "title": "Video Title",
  "description": "Video description...",
  "duration_ms": 360000,
  "thumbnail": "https://i.ytimg.com/vi/...",
  "creator": { "name": "Channel Name", "url": "https://youtube.com/channel/..." },
  "remote_id": "dQw4w9WgXcQ",
  "source_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "view_count": 12345,
  "published_at": "20210101"
}
```

**Note:** `view_count` and `published_at` may be null for search/list results (flat-playlist mode). Use `video.get` on individual videos for complete metadata.
