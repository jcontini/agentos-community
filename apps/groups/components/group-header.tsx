/**
 * Group Header Component
 * 
 * Displays the header for a single group view with icon, name, description,
 * member count, privacy setting, and visit link.
 * Uses primitive CSS patterns (stack, text, image) for theme compatibility.
 */

import React, { useState } from 'react';

export interface GroupHeaderProps {
  /** Group name */
  name?: string;
  /** Group description */
  description?: string;
  /** Group icon/avatar URL */
  icon?: string;
  /** Member count as string (e.g., "2.3K", "78,000") */
  memberCount?: string | number;
  /** Parsed member count as integer */
  memberCountNumeric?: number | null;
  /** Privacy setting */
  privacy?: string;
  /** Group URL */
  url?: string;
  /** Plugin that provided this data (for platform-specific display) */
  plugin?: string;
}

/**
 * Format privacy label
 */
function formatPrivacy(privacy?: string): string {
  switch (privacy) {
    case 'OPEN':
      return 'Public';
    case 'CLOSED':
      return 'Closed';
    case 'SECRET':
      return 'Secret';
    default:
      return 'Public';
  }
}

/**
 * Get platform-specific display name
 * e.g., "r/programming" for Reddit, "Group Name" for Facebook
 */
function getPlatformDisplayName(name?: string, plugin?: string): string | undefined {
  if (!name) return undefined;
  
  switch (plugin) {
    case 'reddit':
      return `r/${name}`;
    case 'facebook':
      return name;
    default:
      return name;
  }
}

/**
 * Format member count for display
 */
function formatMemberCount(count?: string | number): string {
  if (count === undefined || count === null) return '';
  if (typeof count === 'string') return count;
  
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1).replace(/\.0$/, '')}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}K`;
  }
  return count.toString();
}

/**
 * Get initials from name
 */
function getInitials(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length === 0) return '?';
  if (words.length === 1) {
    return words[0].charAt(0).toUpperCase();
  }
  return (words[0].charAt(0) + words[words.length - 1].charAt(0)).toUpperCase();
}

/**
 * Generate consistent color from name
 */
function getColorFromName(name: string): string {
  const colors = [
    '#e57373', '#f06292', '#ba68c8', '#9575cd',
    '#7986cb', '#64b5f6', '#4fc3f7', '#4dd0e1',
    '#4db6ac', '#81c784', '#aed581', '#dce775',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function GroupHeader({
  name,
  description,
  icon,
  memberCount,
  memberCountNumeric,
  privacy,
  url,
  plugin,
}: GroupHeaderProps) {
  const [imageError, setImageError] = useState(false);
  
  const displayName = getPlatformDisplayName(name, plugin);
  const displayMemberCount = formatMemberCount(memberCountNumeric || memberCount);
  const privacyLabel = formatPrivacy(privacy);
  
  const showImage = icon && !imageError;
  const showInitials = !showImage && name;
  
  return (
    <div 
      className="stack" 
      data-direction="horizontal"
      style={{ gap: '12px', padding: '12px', alignItems: 'center' }}
    >
      {/* Compact avatar or initials */}
      {showImage && (
        <img
          className="image"
          data-variant="avatar"
          data-size="md"
          src={icon}
          alt={name || 'Group'}
          onError={() => setImageError(true)}
        />
      )}
      {showInitials && (
        <div
          className="image image--initials"
          data-variant="avatar"
          data-size="md"
          style={{ backgroundColor: getColorFromName(name) }}
          role="img"
          aria-label={name}
        >
          <span className="image__initials">{getInitials(name)}</span>
        </div>
      )}
      
      {/* Info: name + meta + description (compact) */}
      <div 
        className="stack" 
        data-direction="vertical"
        style={{ gap: '2px', flex: 1, minWidth: 0 }}
      >
        {/* Name row with meta */}
        <div 
          className="stack" 
          data-direction="horizontal"
          style={{ gap: '8px', alignItems: 'baseline' }}
        >
          {displayName && url ? (
            <a
              className="text"
              data-variant="title"
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: '1rem', fontWeight: 'bold' }}
            >
              {displayName}
            </a>
          ) : displayName && (
            <span
              className="text"
              style={{ fontSize: '1rem', fontWeight: 'bold' }}
            >
              {displayName}
            </span>
          )}
          
          {/* Inline meta */}
          <span className="text" data-variant="caption">
            {[displayMemberCount && `${displayMemberCount} members`, privacyLabel].filter(Boolean).join(' • ')}
          </span>
        </div>
        
        {/* Description - single line truncated */}
        {description && (
          <span 
            className="text" 
            data-variant="caption"
            style={{ 
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {description}
          </span>
        )}
      </div>
    </div>
  );
}

export default GroupHeader;
