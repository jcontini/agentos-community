---
id: youtube
name: YouTube
description: Get video metadata and transcripts using yt-dlp
icon: icon.png
color: "#FF0808"
website: https://youtube.com

auth: none
connects_to: youtube

# Seed entities: the product and organizations this adapter connects to
seed:
  - id: youtube
    types: [software]
    name: YouTube
    data:
      software_type: platform
      url: https://youtube.com
      launched: "2005"
      platforms: [web, ios, android, macos, windows]
      pricing: free
      wikidata_id: Q866
    relationships:
      - role: offered_by
        to: google

  - id: google
    types: [organization]
    name: Google LLC
    data:
      type: company
      url: https://google.com
      founded: "1998"
      wikidata_id: Q95

  - id: alphabet
    types: [organization]
    name: Alphabet Inc.
    data:
      type: company
      url: https://abc.xyz
      founded: "2015"
      ticker: GOOGL
      exchange: NASDAQ
      wikidata_id: Q21077852
    relationships:
      - role: parent_of
        to: google

instructions: |
  YouTube adapter powered by yt-dlp.
  - No API key needed — uses yt-dlp for metadata and transcripts
  - Search uses yt-dlp's ytsearch (returns up to 50 results)
  - Transcripts extracted from auto-captions when available
  - Channel info extracted as account entities via posted_by relationship

requires:
  - name: yt-dlp
    install:
      macos: brew install yt-dlp
      linux: sudo apt install -y yt-dlp
      windows: choco install yt-dlp -y

# External sources this adapter needs (for CSP)
# Note: Specifying "ytimg.com" allows all subdomains (i.ytimg.com, i9.ytimg.com, etc.)
sources:
  images:
    - ytimg.com            # Video thumbnails (all CDN subdomains)
    - ggpht.com            # Channel avatars (yt3.ggpht.com, etc.)
  frames:
    - https://www.youtube.com          # Embedded video player
    - https://www.youtube-nocookie.com  # Privacy-enhanced embed (better webview compat)

adapters:
  video:
    terminology: Video
    mapping:
      id: .id
      remote_id: .id
      url: .webpage_url
      title: .title
      description: .description
      transcript: .transcript
      transcript_segments: .transcript_segments
      duration_ms: (.duration // null) | if . != null then . * 1000 else null end
      thumbnail: .thumbnail
      published_at: '.upload_date | if . and (. | length) == 8 then (.[0:4] + "-" + .[4:6] + "-" + .[6:8]) else . end'
      resolution: .resolution
      view_count: .view_count
      
      posted_by:
        account:
          id: .channel_id
          platform: '"youtube"'
          handle: .channel
          display_name: .channel
          platform_id: .channel_id
          url: .channel_url

      # Typed reference: creates channel entity for the YouTube channel
      # Direction inferred from upload schema: channel/place(from) → video/work(to)
      posted_in:
        channel:
          id: .channel_id
          name: .channel
          url: .channel_url
          subscriber_count: .channel_follower_count
          platform: '"youtube"'
        _rel:
          type: '"upload"'

      video_post:
        post:
          id: '(.id) + "_post"'
          title: .title
          content: .description
          url: .webpage_url
          published_at: .upload_date
        _rel:
          type: '"embed"'

      transcript_doc:
        document:
          id: '(.id) + "_transcript"'
          title: '"Transcript: " + .title'
          content: .transcript
          url: .webpage_url
        _rel:
          type: '"transcribe"'

      # Typed reference: creates playlist entity for YouTube playlists
      # Direction inferred from add_to schema: playlist/place(from) → video(to)
      in_playlist:
        playlist:
          id: .playlist_id
          name: .playlist
          url: .playlist_url
          platform: '"youtube"'
        _rel:
          type: '"add_to"'
          position: .playlist_index

  post:
    terminology: Comment
    mapping:
      id: .id
      content: .text
      url: '"https://www.youtube.com/watch?v=" + .video_id + "&lc=" + .id'
      published_at: .timestamp | todate
      engagement.likes: .like_count

      posted_by:
        account:
          id: .author_id
          platform: '"youtube"'
          handle: .author
          display_name: .author
          platform_id: .author_id
          url: .author_url
          avatar: .author_thumbnail
        _rel:
          type: '"post"'

      parent_post:
        post:
          id: 'if .parent == "root" then .video_id + "_post" else .parent end'
        _rel:
          type: '"replies_to"'

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
            channel_id: .channel_id,
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
            channel_id: .channel_id,
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
            channel_id: .channel_id,
            channel_url: .channel_url,
            id: .id,
            webpage_url: ("https://www.youtube.com/watch?v=" + .id),
            view_count: .view_count,
            playlist: (if (.playlist_id // "" | startswith("PL")) then .playlist else null end),
            playlist_id: (if (.playlist_id // "" | startswith("PL")) then .playlist_id else null end),
            playlist_index: (if (.playlist_id // "" | startswith("PL")) then .playlist_index else null end),
            playlist_url: (if (.playlist_id // "" | startswith("PL")) then "https://www.youtube.com/playlist?list=" + .playlist_id else null end)
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
    description: |
      Get video transcript with optional timestamps.
      
      Formats:
      - "text" (default): Plain text transcript — best for AI summarization, search, Q&A
      - "segments": Timestamped segments with start_ms/end_ms — use when the user asks about specific moments (e.g., "when do they talk about X?" or "what happens at the 5 minute mark?")
      
      Always returns plain text in the transcript field. The segments format adds a transcript_segments array with timing data.
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
      format:
        type: string
        default: text
        description: "Transcript format: 'text' for plain text (default), 'segments' for timestamped segments"
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - |
          set -e
          TMPDIR=$(mktemp -d)
          trap "rm -rf $TMPDIR" EXIT
          FORMAT="{{params.format}}"
          
          # Download subtitles as JSON3 (YouTube's richest caption format)
          # Try auto-generated first (available on ~85% of videos, has word-level timing)
          yt-dlp --skip-download --write-auto-subs --sub-format json3 --sub-langs "{{params.lang}}" -o "$TMPDIR/sub_%(id)s" "{{params.url}}" >/dev/null 2>&1
          SUBFILE=$(ls "$TMPDIR"/sub_*.json3 2>/dev/null | head -1)
          
          # Fallback: manually uploaded subtitles
          if [ -z "$SUBFILE" ]; then
            yt-dlp --skip-download --write-subs --sub-format json3 --sub-langs "{{params.lang}}" -o "$TMPDIR/sub_%(id)s" "{{params.url}}" >/dev/null 2>&1
            SUBFILE=$(ls "$TMPDIR"/sub_*.json3 2>/dev/null | head -1)
          fi
          
          if [ -z "$SUBFILE" ]; then
            echo '{"error": "No captions available for this video in language: {{params.lang}}"}'
            exit 0
          fi
          
          # Get video metadata
          METADATA=$(yt-dlp --dump-json --skip-download "{{params.url}}" 2>/dev/null)
          
          if [ "$FORMAT" = "segments" ]; then
            # Parse JSON3 into timestamped segments + plain text
            # Each segment: { start_ms, end_ms, text }
            # Filter out empty events and timing markers (events without segs)
            SEGMENTS=$(jq '[
              .events[]
              | select(.segs != null and (.segs | length) > 0)
              | {
                  start_ms: .tStartMs,
                  end_ms: (.tStartMs + .dDurationMs),
                  text: ([.segs[].utf8 // ""] | join("") | gsub("\n"; " ") | gsub("^ +| +$"; ""))
                }
              | select(.text | length > 0)
            ]' "$SUBFILE")
            
            # Derive plain text from segments
            TRANSCRIPT=$(echo "$SEGMENTS" | jq -r '[.[].text] | join(" ") | gsub("  +"; " ")')
            
            # Combine: metadata + transcript + segments
            echo "$METADATA" | jq \
              --arg transcript "$TRANSCRIPT" \
              --argjson segments "$SEGMENTS" \
              '{
                title: .title,
                description: .description,
                transcript: $transcript,
                transcript_segments: $segments,
                duration: .duration,
                thumbnail: .thumbnail,
                channel: .channel,
                channel_id: .channel_id,
                channel_url: .channel_url,
                channel_follower_count: .channel_follower_count,
                id: .id,
                webpage_url: .webpage_url,
                upload_date: .upload_date,
                resolution: .resolution
              }'
          else
            # Default: plain text only (fastest for AI consumption)
            TRANSCRIPT=$(jq -r '
              [.events[] | select(.segs != null) | [.segs[].utf8 // ""] | join("")]
              | join(" ")
              | gsub("\n"; " ")
              | gsub("  +"; " ")
              | gsub("^ +| +$"; "")
            ' "$SUBFILE")
            
            echo "$METADATA" | jq \
              --arg transcript "$TRANSCRIPT" \
              '{
                title: .title,
                description: .description,
                transcript: $transcript,
                duration: .duration,
                thumbnail: .thumbnail,
                channel: .channel,
                channel_id: .channel_id,
                channel_url: .channel_url,
                channel_follower_count: .channel_follower_count,
                id: .id,
                webpage_url: .webpage_url,
                upload_date: .upload_date,
                resolution: .resolution
              }'
          fi
      timeout: 90

  post.list:
    description: |
      List comments on a YouTube video.
      Returns comments as post entities with account attribution and threading.
      Top-level comments reply to the video's post entity. Replies reply to their parent comment.
      Use limit to control how many comments to fetch (default 50, can be slow for popular videos).
    returns: post[]
    web_url: "{{params.url}}"
    params:
      url:
        type: string
        required: true
        description: YouTube video URL
      limit:
        type: integer
        default: 50
        description: Maximum number of comments to fetch
    command:
      binary: bash
      args:
        - "-l"
        - "-c"
        - |
          yt-dlp --skip-download --write-comments --no-write-thumbnail \
            --extractor-args "youtube:max_comments={{params.limit}},all,all,100" \
            --dump-json "{{params.url}}" 2>/dev/null | \
            jq '[.id as $vid | .comments[]? | . + {video_id: $vid}]'
      timeout: 120
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

## Operations

| Operation | Description |
|-----------|-------------|
| `video.search` | Search YouTube videos (sorted by relevance) |
| `video.search_recent` | Search YouTube videos (sorted by upload date, newest first) |
| `video.list` | List videos from a channel or playlist |
| `video.get` | Get full metadata for a single video |
| `video.transcript` | Get video transcript — plain text (default) or timestamped segments |

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

**Linked entities:** Each operation creates account (channel identity) and channel entities in the graph, linked via `posts` and `posted_in` relationships. `video.get` and `video.transcript` additionally create a post entity (social wrapper) and document entity (transcript).

**Note:** `view_count`, `published_at`, and `posted_in.member_count` may be null for search/list results (flat-playlist mode). Use `video.get` on individual videos for complete metadata.
