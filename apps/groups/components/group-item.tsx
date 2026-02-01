/**
 * Group Item Component
 * 
 * Renders a single group in a list view (Facebook Groups, Reddit subreddits, etc.).
 * Uses primitive CSS patterns (stack, text, image) for theme compatibility.
 * 
 * Layout:
 * [avatar] | name (link)
 *          | description preview
 *          | member count • privacy
 */

import React, { useState } from 'react';

interface GroupItemProps {
  /** Group ID */
  id: string;
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
      return '';
  }
}

/**
 * Format member count for display
 */
function formatMemberCount(count?: string | number): string {
  if (count === undefined || count === null) return '';
  
  // If it's already a formatted string, use it
  if (typeof count === 'string') {
    if (count.toLowerCase().includes('member')) return count;
    return `${count} members`;
  }
  
  // Format number with K/M suffixes
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1).replace(/\.0$/, '')}M members`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1).replace(/\.0$/, '')}K members`;
  }
  return `${count} members`;
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

export function GroupItem({
  id,
  name,
  description,
  icon,
  memberCount,
  memberCountNumeric,
  privacy,
  url,
}: GroupItemProps) {
  const [imageError, setImageError] = useState(false);
  
  const displayMemberCount = formatMemberCount(memberCountNumeric || memberCount);
  const privacyLabel = formatPrivacy(privacy);
  
  // Determine if we should show avatar or initials
  const showImage = icon && !imageError;
  const showInitials = !showImage && name;
  
  return (
    <div 
      className="stack" 
      data-direction="horizontal"
      style={{ gap: '12px', padding: '8px 12px', alignItems: 'flex-start' }}
    >
      {/* Avatar or Initials */}
      {showImage && (
        <img
          className="image"
          data-variant="avatar"
          data-size="md"
          src={getProxiedSrc(icon)}
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
      
      {/* Content */}
      <div 
        className="stack" 
        data-direction="vertical"
        style={{ gap: '4px', minWidth: 0, flex: 1 }}
      >
        {/* Name as link */}
        {name && (
          <a
            className="text"
            data-variant="title"
            data-overflow="ellipsis"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          >
            {name}
          </a>
        )}
        
        {/* Description */}
        {description && (
          <span
            className="text"
            data-variant="body"
            data-max-lines="2"
            style={{ 
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {description}
          </span>
        )}
        
        {/* Meta: member count, privacy */}
        {(displayMemberCount || privacyLabel) && (
          <div 
            className="stack" 
            data-direction="horizontal"
            style={{ gap: '6px', alignItems: 'center' }}
          >
            {displayMemberCount && (
              <span className="text" data-variant="caption">
                {displayMemberCount}
              </span>
            )}
            {displayMemberCount && privacyLabel && (
              <span className="text" data-variant="caption">•</span>
            )}
            {privacyLabel && (
              <span className="text" data-variant="caption">
                {privacyLabel}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default GroupItem;
