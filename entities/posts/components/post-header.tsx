/**
 * Post Header Component
 * 
 * Displays the header for a single post detail view.
 * Shows title, author, community, score, and metadata.
 */

import React from 'react';

interface PostHeaderProps {
  /** Post title */
  title?: string;
  /** Author username */
  author?: string;
  /** Author profile URL */
  authorUrl?: string;
  /** Community name */
  community?: string;
  /** Community URL */
  communityUrl?: string;
  /** Score (upvotes - downvotes) */
  score?: number;
  /** Number of comments */
  commentCount?: number;
  /** Publication timestamp */
  publishedAt?: string;
}

/**
 * Format relative time
 */
function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function PostHeader({
  title,
  author,
  authorUrl,
  community,
  communityUrl,
  score,
  commentCount,
  publishedAt,
}: PostHeaderProps) {
  return (
    <div className="post-header">
      {/* Title */}
      {title && (
        <h1 className="post-header__title">{title}</h1>
      )}
      
      {/* Meta info */}
      <div className="post-header__meta">
        {/* Community */}
        {community && (
          communityUrl ? (
            <a 
              href={communityUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="post-header__community"
            >
              {community}
            </a>
          ) : (
            <span className="post-header__community">{community}</span>
          )
        )}
        
        {/* Author */}
        {author && (
          <>
            <span className="post-header__separator">•</span>
            {authorUrl ? (
              <a 
                href={authorUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="post-header__author"
              >
                {author}
              </a>
            ) : (
              <span className="post-header__author">{author}</span>
            )}
          </>
        )}
        
        {/* Time */}
        {publishedAt && (
          <>
            <span className="post-header__separator">•</span>
            <span className="post-header__time">{formatRelativeTime(publishedAt)}</span>
          </>
        )}
      </div>
      
      {/* Engagement stats */}
      <div className="post-header__stats">
        {score !== undefined && (
          <span className="post-header__score">
            {score} points
          </span>
        )}
        {commentCount !== undefined && (
          <span className="post-header__comments">
            {commentCount} comments
          </span>
        )}
      </div>
    </div>
  );
}

export default PostHeader;
