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
import {
  getProxiedSrc,
  getInitials,
  getColorFromString,
  formatCount,
  formatDuration,
  formatRelativeTime,
  getEmbedUrl,
} from '/lib/utils.js';

interface VideoDetailProps {
  entity?: string;
  item?: Record<string, unknown>;
  pending?: boolean;
  error?: string;
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
  if (publishedAt) stats.push(formatRelativeTime(publishedAt));

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
