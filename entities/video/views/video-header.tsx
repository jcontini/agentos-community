/**
 * Video Header Component
 * 
 * Displays a video header with thumbnail, title, creator account,
 * channel/community info, duration, and view count.
 * Uses primitive data-attributes for full theme compatibility.
 * 
 * Layout:
 * [thumbnail 16:9] | title
 *                  | creator (link) • subscribers
 *                  | duration • views
 */

import React, { useState } from 'react';

export interface VideoHeaderProps {
  /** Thumbnail image URL */
  thumbnail?: string;
  /** Video title */
  title: string;
  /** Video URL (makes title clickable) */
  url?: string;
  /** Creator/channel display name (from posted_by account) */
  creator?: string;
  /** Creator profile URL (from posted_by account) */
  creatorUrl?: string;
  /** Channel/community name (from posted_in community) */
  channel?: string;
  /** Channel/community URL (from posted_in community) */
  channelUrl?: string;
  /** Subscriber/member count */
  subscribers?: number;
  /** Duration in milliseconds */
  duration?: number;
  /** View count */
  viewCount?: number;
  /** Optional label to show below duration (e.g., "Transcript") */
  label?: string;
}

/**
 * Format milliseconds to human-readable duration
 * - Under 1 hour: "MM:SS" (e.g., "5:23")
 * - 1 hour+: "H:MM:SS" (e.g., "1:05:23")
 */
function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  
  const pad = (n: number) => n.toString().padStart(2, '0');
  
  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(seconds)}`;
  }
  return `${minutes}:${pad(seconds)}`;
}

/**
 * Format a large number with K/M suffix
 */
function formatCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`;
  }
  return count.toLocaleString();
}

/**
 * Proxy external images through our server to bypass hotlink protection
 */
function getProxiedSrc(src: string | undefined): string | undefined {
  if (!src) return undefined;
  if (src.startsWith('/') || src.startsWith('data:') || src.startsWith('blob:')) {
    return src;
  }
  if (src.startsWith('http://') || src.startsWith('https://')) {
    return `/api/proxy/image?url=${encodeURIComponent(src)}`;
  }
  return src;
}

/**
 * Get initials from title
 */
function getInitials(title: string): string {
  const words = title.trim().split(/\s+/);
  if (words.length === 0) return '▶';
  if (words.length === 1) {
    return words[0].charAt(0).toUpperCase();
  }
  return (words[0].charAt(0) + words[1].charAt(0)).toUpperCase();
}

/**
 * Generate consistent color from title
 */
function getColorFromTitle(title: string): string {
  const colors = [
    '#e57373', '#f06292', '#ba68c8', '#9575cd',
    '#7986cb', '#64b5f6', '#4fc3f7', '#4dd0e1',
    '#4db6ac', '#81c784', '#aed581', '#dce775',
  ];
  let hash = 0;
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function VideoHeader({
  thumbnail,
  title,
  url,
  creator,
  creatorUrl,
  channel,
  channelUrl,
  subscribers,
  duration,
  viewCount,
  label,
}: VideoHeaderProps) {
  const [imageError, setImageError] = useState(false);
  
  // Determine if we should show thumbnail or fallback
  const showImage = thumbnail && !imageError;
  const showFallback = !showImage;

  // Use channel name if creator not available (fallback)
  const displayCreator = creator || channel;
  const displayCreatorUrl = creatorUrl || channelUrl;

  // Build meta line: "17:05 • 10.9M views"
  const metaParts: string[] = [];
  if (duration !== undefined && duration > 0) {
    metaParts.push(formatDuration(duration));
  }
  if (viewCount !== undefined && viewCount > 0) {
    metaParts.push(`${formatCount(viewCount)} views`);
  }
  const metaLine = metaParts.join(' · ');
  
  return (
    <div
      data-component="stack"
      data-direction="horizontal"
      data-gap="xl"
      data-align="start"
    >
      {/* Thumbnail */}
      {showImage && (
        <img
          data-component="image"
          data-variant="thumbnail"
          data-size="lg"
          src={getProxiedSrc(thumbnail)}
          alt={title}
          onError={() => setImageError(true)}
        />
      )}
      {showFallback && (
        <div
          className="image--initials"
          data-variant="thumbnail"
          data-size="lg"
          style={{ backgroundColor: getColorFromTitle(title) }}
          role="img"
          aria-label={title}
        >
          {getInitials(title)}
        </div>
      )}
      
      {/* Metadata */}
      <div
        data-component="stack"
        data-direction="vertical"
        data-gap="sm"
        data-flex="1"
      >
        {/* Title */}
        {url ? (
          <a
            data-component="text"
            data-variant="title"
            data-size="lg"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {title}
          </a>
        ) : (
          <span
            data-component="text"
            data-size="lg"
          >
            {title}
          </span>
        )}
        
        {/* Creator + subscribers */}
        {displayCreator && (
          <div
            data-component="stack"
            data-direction="horizontal"
            data-gap="sm"
            data-align="center"
          >
            {displayCreatorUrl ? (
              <a
                data-component="text"
                data-variant="secondary"
                href={displayCreatorUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {displayCreator}
              </a>
            ) : (
              <span data-component="text" data-variant="secondary">{displayCreator}</span>
            )}
            {subscribers !== undefined && subscribers > 0 && (
              <span data-component="text" data-variant="caption">
                {formatCount(subscribers)} subscribers
              </span>
            )}
          </div>
        )}
        
        {/* Duration + Views */}
        {metaLine && (
          <span data-component="text" data-variant="caption">
            {metaLine}
          </span>
        )}
        
        {/* Optional label (e.g., "Transcript") */}
        {label && (
          <span data-component="text" data-variant="label">
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

export default VideoHeader;
