/**
 * Video Header Component
 * 
 * Displays a video header with thumbnail, title, creator, and duration.
 * Uses primitive CSS patterns (stack, text, image) for theme compatibility.
 * 
 * Layout:
 * [thumbnail 16:9] | title
 *                  | creator (link)
 *                  | duration
 */

import React, { useState } from 'react';

export interface VideoHeaderProps {
  /** Thumbnail image URL */
  thumbnail?: string;
  /** Video title */
  title: string;
  /** Video URL (makes title clickable) */
  url?: string;
  /** Creator/channel name */
  creator?: string;
  /** Creator profile URL (makes name clickable) */
  creatorUrl?: string;
  /** Duration in milliseconds */
  duration?: number;
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
  duration,
  label,
}: VideoHeaderProps) {
  const [imageError, setImageError] = useState(false);
  
  // Determine if we should show thumbnail or fallback
  const showImage = thumbnail && !imageError;
  const showFallback = !showImage;
  
  return (
    <div
      className="stack"
      data-direction="horizontal"
      style={{ gap: '16px', alignItems: 'flex-start' }}
    >
      {/* Thumbnail */}
      {showImage && (
        <img
          className="image"
          data-variant="thumbnail"
          data-size="lg"
          src={getProxiedSrc(thumbnail)}
          alt={title}
          onError={() => setImageError(true)}
          style={{ flexShrink: 0 }}
        />
      )}
      {showFallback && (
        <div
          className="image image--initials"
          data-variant="thumbnail"
          data-size="lg"
          style={{ 
            backgroundColor: getColorFromTitle(title),
            flexShrink: 0,
          }}
          role="img"
          aria-label={title}
        >
          <span className="image__initials">{getInitials(title)}</span>
        </div>
      )}
      
      {/* Metadata */}
      <div
        className="stack"
        data-direction="vertical"
        style={{ gap: '6px', flex: 1, minWidth: 0 }}
      >
        {/* Title */}
        {url ? (
          <a
            className="text"
            data-variant="title"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: '1.125rem', lineHeight: 1.3, textDecoration: 'none' }}
          >
            {title}
          </a>
        ) : (
          <span
            className="text"
            data-variant="title"
            style={{ fontSize: '1.125rem', lineHeight: 1.3 }}
          >
            {title}
          </span>
        )}
        
        {/* Creator */}
        {creator && (
          creatorUrl ? (
            <a
              className="text"
              data-variant="body"
              href={creatorUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ textDecoration: 'none' }}
            >
              {creator}
            </a>
          ) : (
            <span className="text" data-variant="body">{creator}</span>
          )
        )}
        
        {/* Duration */}
        {duration !== undefined && duration > 0 && (
          <span className="text" data-variant="caption">
            {formatDuration(duration)}
          </span>
        )}
        
        {/* Optional label (e.g., "Transcript") */}
        {label && (
          <span className="text" data-variant="section-header" style={{ marginTop: '4px' }}>
            {label}
          </span>
        )}
      </div>
    </div>
  );
}

export default VideoHeader;
