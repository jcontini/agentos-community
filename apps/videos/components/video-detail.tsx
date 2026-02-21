/**
 * Video Detail Component
 *
 * Pure renderer for video entities. Renders:
 * - Embed player (YouTube, Vimeo, etc.)
 * - Title
 * - Channel byline with avatar (from relationship expansion)
 * - Engagement stats (views, likes, date)
 * - Collapsible description
 * - Related entities (transcript, channel)
 *
 * Channel data comes from the system's relationship expansion — when the
 * backend returns a video entity, it automatically includes related entities
 * (like the channel) nested under the relationship key.
 */

import React, { useState } from 'react';

interface VideoDetailProps {
  entity?: string;
  item?: Record<string, unknown>;
  pending?: boolean;
  error?: string;
}

function getProxiedSrc(src: string | undefined): string | undefined {
  if (!src) return undefined;
  if (src.startsWith('data:') || src.startsWith('blob:')) return src;
  if (src.startsWith('//')) return `/ui/proxy/image?url=${encodeURIComponent('https:' + src)}`;
  if (src.startsWith('/')) return src;
  if (src.startsWith('http://') || src.startsWith('https://'))
    return `/ui/proxy/image?url=${encodeURIComponent(src)}`;
  return src;
}

function getEmbedUrl(url: string): string | null {
  const ytMatch = url.match(
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|music\.youtube\.com\/watch\?v=)([\w-]{11})/
  );
  if (ytMatch) {
    const origin = encodeURIComponent(window.location.origin);
    return `https://www.youtube-nocookie.com/embed/${ytMatch[1]}?origin=${origin}`;
  }
  const vimeoMatch = url.match(/vimeo\.com\/(\d+)/);
  if (vimeoMatch) return `https://player.vimeo.com/video/${vimeoMatch[1]}`;
  return null;
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 10_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  return n.toLocaleString();
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function getInitials(name: string): string {
  return name
    .split(/[\s_-]+/)
    .slice(0, 2)
    .map(w => w[0]?.toUpperCase() || '')
    .join('');
}

function getColorFromString(text: string): string {
  const colors = [
    '#e57373', '#f06292', '#ba68c8', '#9575cd',
    '#7986cb', '#64b5f6', '#4fc3f7', '#4dd0e1',
    '#4db6ac', '#81c784', '#aed581', '#dce775',
  ];
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    hash = text.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export default function VideoDetail({ entity, item, pending, error }: VideoDetailProps) {
  const [descExpanded, setDescExpanded] = useState(false);

  // Channel data comes from relationship expansion — the system includes
  // related entities in the response (e.g., upload.channel for videos).
  const channel = item?.upload
    ? (item.upload as Record<string, unknown>)?.channel as Record<string, unknown> | undefined
    : undefined;
  const channelUrl = channel?.url as string | undefined;
  const channelThumbnail = (channel?.icon || channel?.thumbnail) as string | undefined;
  const channelName = channel?.name as string | undefined;
  const subscriberCount = channel?.subscriber_count as number | undefined;

  // Lazy enrichment: if channel has no avatar, fetch it in the background
  React.useEffect(() => {
    if (channelUrl && !channelThumbnail) {
      // Fire and forget — the backend handles the entity update
      fetch('/use/youtube/channel.get', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Agent': 'videos-app',
        },
        body: JSON.stringify({ url: channelUrl }),
      }).catch(() => {
        // Silently fail — not critical to app functionality
      });
    }
  }, [channelUrl, channelThumbnail]);

  if (pending) {
    return (
      <div className="entity-detail">
        <div className="entity-detail-empty">
          <span style={{ opacity: 0.5 }}>Loading...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="entity-detail">
        <div className="entity-detail-error">
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="entity-detail">
        <div className="entity-detail-empty">
          <span style={{ opacity: 0.5 }}>No video data</span>
        </div>
      </div>
    );
  }

  const url = item.url as string | undefined;
  const embedUrl = url ? getEmbedUrl(url) : null;
  const title = item.title as string | undefined;
  const description = item.description as string | undefined;
  const viewCount = item.view_count as number | undefined;
  const likeCount = item.like_count as number | undefined;
  const publishedAt = item.published_at as string | undefined;
  const durationMs = item.duration_ms as number | undefined;

  // Build stats segments — null fields are omitted
  const stats: string[] = [];
  if (viewCount != null) stats.push(`${formatCount(viewCount)} views`);
  if (likeCount != null) stats.push(`${formatCount(likeCount)} likes`);
  if (durationMs != null) stats.push(formatDuration(durationMs));
  if (publishedAt) stats.push(formatDate(publishedAt));

  // Related entities
  const transcript = item.transcribe
    ? (item.transcribe as Record<string, unknown>)?.document as Record<string, unknown> | undefined
    : undefined;

  return (
    <div className="entity-detail">
      {/* Embed player */}
      {embedUrl ? (
        <div className="entity-detail-embed">
          <iframe
            className="entity-detail-embed-iframe"
            src={embedUrl}
            title={title || 'Video'}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      ) : null}

      <div className="entity-detail-content" style={{ padding: '16px' }}>
        {/* Title */}
        {title ? <h2 className="entity-detail-title">{title}</h2> : null}

        {/* Channel byline + actions */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {/* Channel avatar or initials */}
            {channelThumbnail ? (
              <img
                src={getProxiedSrc(channelThumbnail)}
                alt={channelName || ''}
                style={{ width: 40, height: 40, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            ) : channelName ? (
              <div
                style={{
                  width: 40, height: 40, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, fontWeight: 500, flexShrink: 0,
                  backgroundColor: getColorFromString(channelName), color: '#fff',
                }}
              >
                {getInitials(channelName)}
              </div>
            ) : null}

            <div>
              {channelName ? (
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--content-fg)' }}>
                  {channelName}
                </div>
              ) : null}
              {subscriberCount != null ? (
                <div style={{ fontSize: 12, color: 'var(--content-fg-muted)', marginTop: 2 }}>
                  {formatCount(subscriberCount)} subscribers
                </div>
              ) : null}
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            {url ? (
              <button
                className="entity-detail-reference"
                style={{
                  cursor: 'pointer',
                  padding: '6px 12px',
                  fontSize: 12,
                  border: '1px solid var(--content-border-subtle)',
                  borderRadius: 6,
                  background: 'var(--content-bg)',
                  color: 'var(--content-fg)',
                }}
                onClick={() => navigator.clipboard.writeText(url)}
              >
                Copy Link
              </button>
            ) : null}
          </div>
        </div>

        {/* Stats line */}
        {stats.length > 0 ? (
          <div style={{ fontSize: 12, color: 'var(--content-fg-muted)', marginTop: 12 }}>
            {stats.join(' \u00B7 ')}
          </div>
        ) : null}

        {/* Description (collapsible) */}
        {description ? (
          <div className="entity-detail-section" style={{ marginTop: 16 }}>
            <div
              className="entity-detail-text-block"
              style={{
                whiteSpace: 'pre-wrap',
                ...(descExpanded ? {} : { maxHeight: 72, overflow: 'hidden' }),
              }}
            >
              {description}
            </div>
            {description.length > 200 ? (
              <button
                onClick={() => setDescExpanded(!descExpanded)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  marginTop: 4,
                  fontSize: 12,
                  color: 'var(--link-color-subtle)',
                  cursor: 'pointer',
                }}
              >
                {descExpanded ? 'Show less' : 'Show more'}
              </button>
            ) : null}
          </div>
        ) : null}

        {/* Related entities */}
        {(transcript || channel) ? (
          <div className="entity-detail-section" style={{ marginTop: 16 }}>
            <div className="entity-detail-section-title">Related</div>
            <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
              {transcript ? (
                <span className="entity-detail-reference">
                  <span className="entity-detail-reference-type">Transcript</span>
                </span>
              ) : null}
              {channel ? (
                <span className="entity-detail-reference">
                  <span className="entity-detail-reference-type">Channel</span>
                  <span className="entity-detail-reference-name" style={{ marginLeft: 4 }}>
                    {channelName || 'Unknown'}
                  </span>
                </span>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
