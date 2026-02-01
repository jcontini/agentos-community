/**
 * Community Header Component
 * 
 * Displays a breadcrumb-style header showing which community/subreddit
 * the posts belong to. Used in list views to provide context.
 * Uses primitive data-attributes for full theme compatibility.
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
      data-component="stack"
      data-padding="lg"
      data-header-bar
    >
      {communityUrl ? (
        <a
          data-component="text"
          data-variant="title"
          data-size="lg"
          data-weight="bold"
          href={communityUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          {displayName}
        </a>
      ) : (
        <span
          data-component="text"
          data-size="lg"
          data-weight="bold"
        >
          {displayName}
        </span>
      )}
    </div>
  );
}

export default CommunityHeader;
