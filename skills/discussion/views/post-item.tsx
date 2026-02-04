/**
 * Post Item Component
 * 
 * Renders a single post in a list view (Reddit, HN, Twitter, etc.).
 * Uses primitive data-attributes for full theme compatibility.
 * 
 * Layout:
 * [score] | title (link)
 *         | community · author · time · comments
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
  /** Permalink URL (discussion page) */
  url?: string;
  /** External link target (article being linked to) */
  externalUrl?: string;
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

/**
 * Format score with K/M suffixes
 */
function formatScore(score: number): string {
  if (score >= 1000000) {
    return `${(score / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
  }
  if (score >= 10000) {
    return `${(score / 1000).toFixed(1).replace(/\.0$/, '')}K`;
  }
  if (score >= 1000) {
    return `${(score / 1000).toFixed(1)}K`;
  }
  return String(score);
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
  externalUrl,
  publishedAt,
}: PostItemProps) {
  // Title links to external article if available, otherwise to discussion
  const titleHref = externalUrl || url;
  // Use title if available, otherwise truncate content
  const displayTitle = title || (content ? content.slice(0, 100) + (content.length > 100 ? '...' : '') : 'Untitled');
  
  // Build meta items array for clean separator handling
  const metaItems: React.ReactNode[] = [];
  if (community) {
    metaItems.push(
      <span key="community" data-component="text" data-variant="caption">
        r/{community}
      </span>
    );
  }
  if (author) {
    metaItems.push(
      <span key="author" data-component="text" data-variant="caption">
        by {author}
      </span>
    );
  }
  if (publishedAt) {
    metaItems.push(
      <span key="time" data-component="text" data-variant="caption">
        {formatRelativeTime(publishedAt)}
      </span>
    );
  }
  if (commentCount !== undefined) {
    // Make comments a link to discussion when we have an external URL
    metaItems.push(
      externalUrl && url ? (
        <a
          key="comments"
          data-component="text"
          data-variant="caption"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {commentCount} comments
        </a>
      ) : (
        <span key="comments" data-component="text" data-variant="caption">
          {commentCount} comments
        </span>
      )
    );
  }
  
  // Interleave with separators
  const metaWithSeparators: React.ReactNode[] = [];
  metaItems.forEach((item, index) => {
    if (index > 0) {
      metaWithSeparators.push(
        <span key={`sep-${index}`} data-component="text" data-variant="caption">·</span>
      );
    }
    metaWithSeparators.push(item);
  });
  
  return (
    <div
      data-component="stack"
      data-direction="horizontal"
      data-gap="lg"
      data-padding="md"
      data-align="start"
    >
      {/* Score column */}
      {score !== undefined && (
        <div
          data-component="stack"
          data-direction="vertical"
          data-gap="none"
          data-align="center"
          data-score-column
        >
          <span data-component="text" data-variant="muted" data-size="xs">▲</span>
          <span data-component="text" data-variant="caption" data-weight="bold">
            {formatScore(score)}
          </span>
        </div>
      )}
      
      {/* Content */}
      <div
        data-component="stack"
        data-direction="vertical"
        data-gap="xs"
        data-flex="1"
      >
        {/* Title as link - goes to external article if available */}
        <a
          data-component="text"
          data-variant="title"
          data-overflow="ellipsis"
          href={titleHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          {displayTitle}
        </a>
        
        {/* Meta line */}
        {metaWithSeparators.length > 0 && (
          <div
            data-component="stack"
            data-direction="horizontal"
            data-gap="sm"
            data-align="center"
            data-wrap="wrap"
          >
            {metaWithSeparators}
          </div>
        )}
      </div>
    </div>
  );
}

export default PostItem;
