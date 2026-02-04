/**
 * Post Header Component
 * 
 * Displays the header for a single post view with title, author,
 * community, score, comment count, and timestamp.
 * Uses primitive data-attributes for full theme compatibility.
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
      data-component="stack"
      data-direction="vertical"
      data-gap="md"
      data-padding="lg"
    >
      {/* Title */}
      {title && (
        <span
          data-component="text"
          data-size="xl"
          data-weight="medium"
        >
          {title}
        </span>
      )}
      
      {/* Meta line: author • time */}
      <div
        data-component="stack"
        data-direction="horizontal"
        data-gap="sm"
        data-align="center"
        data-wrap="wrap"
      >
        {/* Author */}
        {author && (
          <>
            <span data-component="text" data-variant="caption">Posted by</span>
            {authorUrl ? (
              <a
                data-component="text"
                data-variant="caption"
                href={authorUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                {author}
              </a>
            ) : (
              <span data-component="text" data-variant="caption">{author}</span>
            )}
          </>
        )}
        
        {/* Separator */}
        {author && publishedAt && (
          <span data-component="text" data-variant="caption">•</span>
        )}
        
        {/* Time */}
        {publishedAt && (
          <span data-component="text" data-variant="caption">
            {formatRelativeTime(publishedAt)}
          </span>
        )}
      </div>
      
      {/* Stats line: score · comments */}
      {(score !== undefined || commentCount !== undefined) && (
        <div
          data-component="stack"
          data-direction="horizontal"
          data-gap="lg"
          data-align="center"
        >
          {score !== undefined && (
            <span data-component="text" data-variant="caption">
              <strong>{formatNumber(score)}</strong> points
            </span>
          )}
          {commentCount !== undefined && (
            <span data-component="text" data-variant="caption">
              <strong>{formatNumber(commentCount)}</strong> comments
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export default PostHeader;
