/**
 * Video Search Result Component
 * 
 * Renders a single video search result (YouTube, Vimeo, etc.).
 * Uses primitive CSS patterns (stack, text, image) for theme compatibility.
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
  source_url?: string;
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
  source_url,
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
      className="stack"
      data-direction="horizontal"
      style={{ gap: '12px', padding: '8px 12px', alignItems: 'flex-start' }}
    >
      {/* Thumbnail */}
      {showImage && (
        <img
          className="image"
          data-variant="thumbnail"
          data-size="sm"
          src={getProxiedSrc(thumbnail)}
          alt=""
          onError={() => setImageError(true)}
          style={{ flexShrink: 0, width: '120px', height: '68px', objectFit: 'cover', borderRadius: '4px' }}
        />
      )}
      {showFallback && (
        <div
          className="image image--initials"
          data-variant="thumbnail"
          data-size="sm"
          style={{ 
            backgroundColor: getColorFromTitle(title),
            flexShrink: 0,
            width: '120px',
            height: '68px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          role="img"
          aria-hidden="true"
        >
          <span className="image__initials" style={{ fontSize: '1.5rem' }}>{getInitials(title)}</span>
        </div>
      )}
      
      {/* Content */}
      <div
        className="stack"
        data-direction="vertical"
        style={{ gap: '4px', flex: 1, minWidth: 0 }}
      >
        {/* Title */}
        {source_url ? (
          <a
            className="text"
            data-variant="title"
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ 
              overflow: 'hidden', 
              textOverflow: 'ellipsis', 
              whiteSpace: 'nowrap',
              textDecoration: 'none',
            }}
          >
            {title}
          </a>
        ) : (
          <span
            className="text"
            data-variant="title"
            style={{ 
              overflow: 'hidden', 
              textOverflow: 'ellipsis', 
              whiteSpace: 'nowrap',
            }}
          >
            {title}
          </span>
        )}
        
        {/* Creator */}
        {creator_name && (
          creator_url ? (
            <a
              className="text"
              data-variant="body"
              href={creator_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ 
                textDecoration: 'none',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {creator_name}
            </a>
          ) : (
            <span
              className="text"
              data-variant="body"
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {creator_name}
            </span>
          )
        )}
        
        {/* Duration + Views */}
        {metaLine && (
          <span className="text" data-variant="caption">
            {metaLine}
          </span>
        )}
        
        {/* Description (optional, truncated) */}
        {description && (
          <span
            className="text"
            data-variant="body"
            style={{ 
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              opacity: 0.8,
            }}
          >
            {description}
          </span>
        )}
      </div>
    </div>
  );
}

export default VideoSearchResult;
