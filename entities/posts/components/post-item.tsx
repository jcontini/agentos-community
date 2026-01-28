/**
 * Post Item Component
 * 
 * Renders a single post in a list view (Reddit, HN, Twitter, etc.).
 * Shows title, author, community, score, and comment count.
 */

import React from 'react';

interface PostItemProps {
  /** Post ID */
  id: string;
  /** Post title (may be empty for comments/tweets) */
  title?: string;
  /** Post body/content */
  content?: string;
  /** Author username */
  author?: string;
  /** Community/subreddit name */
  community?: string;
  /** Score (upvotes - downvotes) */
  score?: number;
  /** Number of comments */
  commentCount?: number;
  /** Permalink URL */
  url?: string;
  /** Publication timestamp */
  publishedAt?: string;
}

/**
 * Format relative time (e.g., "5h ago", "2d ago")
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

export function PostItem({
  id,
  title,
  content,
  author,
  community,
  score,
  commentCount,
  url,
  publishedAt,
}: PostItemProps) {
  // Use title if available, otherwise truncate content
  const displayTitle = title || (content ? content.slice(0, 100) + (content.length > 100 ? '...' : '') : 'Untitled');
  
  return (
    <div className="post-item">
      {/* Score on left */}
      {score !== undefined && (
        <div className="post-item__score">
          {score}
        </div>
      )}
      
      <div className="post-item__content">
        {/* Title/link */}
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="post-item__title"
        >
          {displayTitle}
        </a>
        
        {/* Meta line: community, author, time, comments */}
        <div className="post-item__meta">
          {community && (
            <span className="post-item__community">{community}</span>
          )}
          {author && (
            <span className="post-item__author">by {author}</span>
          )}
          {publishedAt && (
            <span className="post-item__time">{formatRelativeTime(publishedAt)}</span>
          )}
          {commentCount !== undefined && (
            <span className="post-item__comments">{commentCount} comments</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default PostItem;
