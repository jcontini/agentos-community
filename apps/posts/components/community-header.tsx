/**
 * Community Header Component
 * 
 * Displays a breadcrumb-style header showing which community/subreddit
 * the posts belong to. Used in list views to provide context.
 */

import React from 'react';

export interface CommunityHeaderProps {
  /** Community name */
  name?: string;
  /** Community URL */
  url?: string;
  /** Plugin that provided this data (for platform-specific display) */
  plugin?: string;
}

/**
 * Get platform-specific community display name
 * e.g., "r/programming" for Reddit
 */
function formatCommunity(name?: string, plugin?: string): string | undefined {
  if (!name) return undefined;
  
  switch (plugin) {
    case 'reddit':
      return `r/${name}`;
    default:
      return name;
  }
}

/**
 * Get platform-specific community URL
 */
function getCommunityUrl(name?: string, plugin?: string, providedUrl?: string): string | undefined {
  if (providedUrl) return providedUrl;
  if (!name) return undefined;
  
  switch (plugin) {
    case 'reddit':
      return `https://reddit.com/r/${name}`;
    default:
      return undefined;
  }
}

export function CommunityHeader({
  name,
  url,
  plugin,
}: CommunityHeaderProps) {
  const displayName = formatCommunity(name, plugin);
  const communityUrl = getCommunityUrl(name, plugin, url);
  
  if (!displayName) return null;
  
  return (
    <div
      style={{
        padding: '12px 16px',
        borderBottom: '1px solid rgba(0, 0, 0, 0.1)',
      }}
    >
      {communityUrl ? (
        <a
          className="text"
          data-variant="title"
          href={communityUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '1rem',
          }}
        >
          {displayName}
        </a>
      ) : (
        <span
          className="text"
          data-variant="title"
          style={{
            fontWeight: 600,
            fontSize: '1rem',
          }}
        >
          {displayName}
        </span>
      )}
    </div>
  );
}

export default CommunityHeader;
