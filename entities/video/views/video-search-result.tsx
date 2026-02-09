/**
 * Video Search Result Component
 * 
 * Renders a single video search result (YouTube, Vimeo, etc.).
 * Uses primitive data-attributes for full theme compatibility.
 * 
 * Layout:
 * [thumbnail] | title (link)
 *             | creator
 *             | duration • views
 */

import React, { useState } from 'react';

interface VideoSearchResultProps {
  /** Video title */
  title: string;
  /** Video URL */
  url?: string;
  /** Thumbnail image URL */
  thumbnail?: string;
  /** Creator/channel name */
  creator_name?: string;
  /** Creator profile URL */
  creator_url?: string;
  /** Duration in milliseconds */
  duration_ms?: number;
  /** View count */
  view_count?: number;
  /** Description/snippet */
  description?: string;
}

/**
 * Format milliseconds to human-readable duration
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
 * Format view count with K/M suffix
 */
function formatViews(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M views`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K views`;
  }
  return `${count} views`;
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

export function VideoSearchResult({
  title,
  url,
  thumbnail,
  creator_name,
  creator_url,
  duration_ms,
  view_count,
  description,
}: VideoSearchResultProps) {
  const [imageError, setImageError] = useState(false);
  
  const showImage = thumbnail && !imageError;
  const showFallback = !showImage;
  
  // Build metadata line: "5:23 • 1.2M views"
  const metaParts: string[] = [];
  if (duration_ms && duration_ms > 0) {
    metaParts.push(formatDuration(duration_ms));
  }
  if (view_count && view_count > 0) {
    metaParts.push(formatViews(view_count));
  }
  const metaLine = metaParts.join(' • ');
  
  return (
    <div
      data-component="stack"
      data-direction="horizontal"
      data-gap="lg"
      data-padding="md"
      data-align="start"
    >
      {/* Thumbnail */}
      {showImage && (
        <img
          data-component="image"
          data-variant="thumbnail"
          data-size="md"
          src={getProxiedSrc(thumbnail)}
          alt=""
          onError={() => setImageError(true)}
        />
      )}
      {showFallback && (
        <div
          className="image--initials"
          data-variant="thumbnail"
          data-size="md"
          style={{ backgroundColor: getColorFromTitle(title) }}
          role="img"
          aria-hidden="true"
        >
          {getInitials(title)}
        </div>
      )}
      
      {/* Content */}
      <div
        data-component="stack"
        data-direction="vertical"
        data-gap="xs"
        data-flex="1"
      >
        {/* Title */}
        {url ? (
          <a
            data-component="text"
            data-variant="title"
            data-overflow="ellipsis"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {title}
          </a>
        ) : (
          <span
            data-component="text"
            data-overflow="ellipsis"
          >
            {title}
          </span>
        )}
        
        {/* Creator */}
        {creator_name && (
          creator_url ? (
            <a
              data-component="text"
              data-variant="secondary"
              data-overflow="ellipsis"
              href={creator_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {creator_name}
            </a>
          ) : (
            <span
              data-component="text"
              data-variant="secondary"
              data-overflow="ellipsis"
            >
              {creator_name}
            </span>
          )
        )}
        
        {/* Duration + Views */}
        {metaLine && (
          <span data-component="text" data-variant="caption">
            {metaLine}
          </span>
        )}
        
        {/* Description (optional, truncated) */}
        {description && (
          <span
            data-component="text"
            data-variant="muted"
            data-lines="2"
          >
            {description}
          </span>
        )}
      </div>
    </div>
  );
}

export default VideoSearchResult;
