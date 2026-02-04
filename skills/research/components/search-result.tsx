/**
 * Search Result Component
 * 
 * Renders a single web search result (Exa, Firecrawl, etc.).
 * Uses primitive data-attributes for full theme compatibility.
 * 
 * Layout:
 * [favicon] | title (link)
 *           | url (truncated)
 *           | snippet (2-3 lines)
 */

import React, { useState } from 'react';

interface SearchResultProps {
  /** Result title - displayed prominently */
  title: string;
  /** Result URL - displayed below title */
  url: string;
  /** Optional snippet/description */
  snippet?: string;
  /** Optional favicon URL */
  favicon?: string;
}

/**
 * Extract domain from URL for display
 */
function extractDomain(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
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
 * Get initials from domain name
 */
function getInitials(domain: string): string {
  // Take first letter of domain
  return domain.charAt(0).toUpperCase();
}

/**
 * Generate consistent color from domain
 */
function getColorFromDomain(domain: string): string {
  const colors = [
    '#e57373', '#f06292', '#ba68c8', '#9575cd',
    '#7986cb', '#64b5f6', '#4fc3f7', '#4dd0e1',
    '#4db6ac', '#81c784', '#aed581', '#dce775',
  ];
  let hash = 0;
  for (let i = 0; i < domain.length; i++) {
    hash = domain.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function SearchResult({
  title,
  url,
  snippet,
  favicon,
}: SearchResultProps) {
  const [imageError, setImageError] = useState(false);
  const domain = extractDomain(url);
  
  // Determine if we should show favicon or initials
  const showImage = favicon && !imageError;
  const showInitials = !showImage;
  
  return (
    <div
      data-component="stack"
      data-direction="horizontal"
      data-gap="lg"
      data-padding="md"
      data-align="start"
    >
      {/* Favicon or initials */}
      {showImage && (
        <img
          data-component="image"
          data-variant="icon"
          data-size="sm"
          src={getProxiedSrc(favicon)}
          alt=""
          onError={() => setImageError(true)}
        />
      )}
      {showInitials && (
        <div
          className="image--initials"
          data-variant="icon"
          data-size="sm"
          style={{ backgroundColor: getColorFromDomain(domain) }}
          role="img"
          aria-hidden="true"
        >
          {getInitials(domain)}
        </div>
      )}
      
      {/* Content */}
      <div
        data-component="stack"
        data-direction="vertical"
        data-gap="xs"
        data-flex="1"
      >
        {/* Title as link */}
        <a
          data-component="text"
          data-variant="title"
          data-overflow="ellipsis"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
        >
          {title || domain}
        </a>
        
        {/* URL */}
        <span
          data-component="text"
          data-variant="url"
          data-overflow="ellipsis"
        >
          {url}
        </span>
        
        {/* Snippet */}
        {snippet && (
          <span
            data-component="text"
            data-variant="secondary"
            data-lines="2"
          >
            {snippet}
          </span>
        )}
      </div>
    </div>
  );
}

export default SearchResult;
