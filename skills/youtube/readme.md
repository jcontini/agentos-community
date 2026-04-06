---
id: youtube
name: YouTube
description: Get video metadata and transcripts using yt-dlp
color: "#FF0808"
website: "https://youtube.com"

sources:
  images:
  - ytimg.com
  - ggpht.com
  - googleusercontent.com
  frames:
  - https://www.youtube.com
  - https://www.youtube-nocookie.com

operations:
  search_videos:
    web_url: https://www.youtube.com/results?search_query=${PARAM_QUERY}
  search_recent_video:
    web_url: https://www.youtube.com/results?search_query=${PARAM_QUERY}&sp=CAI
  list_videos:
    handles_urls:
    - youtube.com/@*
    - youtube.com/channel/*
    - youtube.com/c/*
    - youtube.com/playlist*
    web_url: .params.url
  get_video:
    handles_urls:
    - youtube.com/*
    - youtu.be/*
    - music.youtube.com/*
    web_url: .params.url
  transcript_video:
    web_url: .params.url
  get_channel:
    handles_urls:
    - youtube.com/@*
    - youtube.com/channel/*
    - youtube.com/c/*
  list_posts:
    web_url: .params.url
---

# YouTube

YouTube adapter for searching, browsing, and getting video metadata. Uses `yt-dlp` for all operations — no API key required.

## Requirements

Install yt-dlp:

```bash
brew install yt-dlp    # macOS
apt install yt-dlp     # Linux
choco install yt-dlp   # Windows
```

## Usage

| Operation | Description |
|-----------|-------------|
| `search_videos` | Search YouTube videos (sorted by relevance) |
| `search_recent_video` | Search YouTube videos (sorted by upload date, newest first) |
| `list_videos` | List videos from a channel or playlist |
| `get_video` | Get full metadata for a single video |
| `transcript_video` | Get video transcript — plain text (default) or timestamped segments |
| `get_channel` | Get channel metadata (avatar, description, subscriber count) |

## video.search

Search YouTube videos sorted by relevance. Returns 10 results.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `query` | string | Search query |

**Example:**

```bash
POST /api/adapters/youtube/video.search
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
POST /api/adapters/youtube/video.search_recent
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
POST /api/adapters/youtube/video.list
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

Get video transcript with optional timestamps. Powered by YouTube's JSON3 caption format.

**Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | YouTube video URL |
| `lang` | string | `"en"` | Language code (en, es, fr, etc.) |
| `format` | string | `"text"` | `"text"` for plain text, `"segments"` for timestamped segments |

**When to use each format:**
- `text` — AI summarization, search, Q&A ("what is this video about?")
- `segments` — Temporal navigation ("when do they start talking about X?", "what happens at the 5 minute mark?")

**Segments format response** (in addition to standard video fields):

```json
{
  "transcript": "plain text always included...",
  "transcript_segments": [
    { "start_ms": 0, "end_ms": 4500, "text": "Welcome to today's video" },
    { "start_ms": 4500, "end_ms": 8200, "text": "We're going to talk about linear algebra" },
    { "start_ms": 8200, "end_ms": 12000, "text": "and why it's so fundamental" }
  ]
}
```

Segments are typically 2-5 seconds each. Timestamps are in milliseconds. Uses auto-generated captions when available, falls back to manually uploaded subtitles.

## channel.get

Get channel metadata including avatar, banner, description, and subscriber count. Used for lazy enrichment — when a video is opened and the channel entity is missing rich data, this operation fills it in.

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `url` | string | YouTube channel URL |

**Supported URL formats:**
- `https://www.youtube.com/@channelname`
- `https://www.youtube.com/channel/UCxxxxxxx`
- `https://www.youtube.com/c/channelname`

**Returns:**

```json
{
  "id": "UCxxxxxxx",
  "name": "Channel Name",
  "url": "https://www.youtube.com/channel/UCxxxxxxx",
  "description": "Channel description...",
  "subscriber_count": 6100000,
  "avatar": "https://yt3.googleusercontent.com/ytc/...",
  "banner": "https://yt3.googleusercontent.com/...",
  "platform": "youtube"
}
```

## Response Schema

All operations return videos with these fields:

```json
{
  "title": "Video Title",
  "description": "Video description...",
  "duration_ms": 360000,
  "thumbnail": "https://i.ytimg.com/vi/...",
  "remote_id": "dQw4w9WgXcQ",
  "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
  "view_count": 12345,
  "published_at": "20210101",
  "posted_by": {
    "display_name": "Channel Name",
    "handle": "Channel Name",
    "platform": "youtube",
    "platform_id": "UCxxxxxx",
    "url": "https://youtube.com/channel/UCxxxxxx"
  },
  "posted_in": {
    "name": "Channel Name",
    "url": "https://youtube.com/channel/UCxxxxxx",
    "member_count": 1234000
  }
}
```

**Linked entities:** Each operation creates account (channel identity) and channel entities on the graph, linked via `posts` and `posted_in` relationships. `get_video` and `transcript_video` additionally create a post entity (social wrapper) and document entity (transcript).

**Note:** `view_count`, `published_at`, and `posted_in.member_count` may be null for search/list results (flat-playlist mode). Use `get_video` on individual videos for complete metadata.
