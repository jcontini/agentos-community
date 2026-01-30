/**
 * Post Header Component
 * 
 * Displays the header for a single post view with title, author,
 * community, score, comment count, and timestamp.
 * Uses primitive CSS patterns (stack, text) for theme compatibility.
 * 
 * Layout:
 * title
 * community • Posted by author • time
 * score points · comments comments
 */

import React from 'react';

export interface PostHeaderProps {
  /** Post title */
  title?: string;
  /** Author username */
  author?: string;
  /** Author profile URL */
  authorUrl?: string;
  /** Score (upvotes - downvotes) */
  score?: number;
  /** Number of comments */
  commentCount?: number;
  /** Publication timestamp */
  publishedAt?: string;
}

/**
 * Format relative time (e.g., "5 hours ago", "2 days ago")
 */
function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 60) return `${diffMins} minutes ago`;
  if (diffHours < 24) return `${diffHours} hours ago`;
  if (diffDays < 30) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

/**
 * Format large numbers with K/M suffixes
 */
function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1).replace(/\.0$/, '')}K`;
  }
  return String(num);
}

export function PostHeader({
  title,
  author,
  authorUrl,
  score,
  commentCount,
  publishedAt,
}: PostHeaderProps) {
  return (
    <div
      className="stack"
      data-direction="vertical"
      style={{ gap: '8px', padding: '12px 16px' }}
    >
      {/* Title */}
      {title && (
        <span
          className="text"
          data-variant="title"
          style={{ fontSize: '1.25rem', lineHeight: 1.3 }}
        >
          {title}
        </span>
      )}
      
      {/* Meta line: author • time */}
      <div
        className="stack"
        data-direction="horizontal"
        style={{ gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}
      >
        {/* Author */}
        {author && (
          <>
            <span className="text" data-variant="caption">Posted by</span>
            {authorUrl ? (
              <a
                className="text"
                data-variant="caption"
                href={authorUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: 'none' }}
              >
                {author}
              </a>
            ) : (
              <span className="text" data-variant="caption">{author}</span>
            )}
          </>
        )}
        
        {/* Separator */}
        {author && publishedAt && (
          <span className="text" data-variant="caption">•</span>
        )}
        
        {/* Time */}
        {publishedAt && (
          <span className="text" data-variant="caption">
            {formatRelativeTime(publishedAt)}
          </span>
        )}
      </div>
      
      {/* Stats line: score · comments */}
      {(score !== undefined || commentCount !== undefined) && (
        <div
          className="stack"
          data-direction="horizontal"
          style={{ gap: '12px', alignItems: 'center' }}
        >
          {score !== undefined && (
            <span className="text" data-variant="caption">
              <strong>{formatNumber(score)}</strong> points
            </span>
          )}
          {commentCount !== undefined && (
            <span className="text" data-variant="caption">
              <strong>{formatNumber(commentCount)}</strong> comments
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default PostHeader;
