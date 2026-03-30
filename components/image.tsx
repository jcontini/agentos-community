/**
 * Image Primitive Component
 * 
 * The foundational component for all image rendering. Handles variants,
 * sizing, fallbacks, and error states — so themes only need to style
 * appearance.
 * 
 * Why a dedicated Image primitive?
 * - Avatars need circular cropping and fallback initials
 * - Thumbnails need aspect ratio enforcement
 * - Icons need consistent sizing
 * - Error handling (broken images) is centralized
 * 
 * @example
 * ```yaml
 * - component: image
 *   props:
 *     src: "{{icon}}"
 *     variant: avatar
 *     size: md
 *     fallback: initials
 *     name: "{{name}}"
 * ```
 */

import React, { useState } from 'react';

export interface ImageProps {
  /** Image source URL */
  src?: string;
  
  /** Alt text for accessibility */
  alt?: string;
  
  /** Visual variant (affects default styling) */
  variant?: 'avatar' | 'thumbnail' | 'icon' | 'cover';
  
  /** Size preset */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  
  /** Fallback behavior when image fails or is missing */
  fallback?: 'initials' | 'icon' | 'none';
  
  /** Name for initials fallback (e.g., "Programming Group" → "PG") */
  name?: string;
  
  /** Additional CSS class */
  className?: string;
}

/**
 * Extract initials from a name
 * - "Programming Group" → "PG"
 * - "rust" → "R"
 * - "John Doe Smith" → "JS" (first and last)
 */
function getInitials(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length === 0) return '?';
  if (words.length === 1) {
    return words[0].charAt(0).toUpperCase();
  }
  // First and last word initials
  return (words[0].charAt(0) + words[words.length - 1].charAt(0)).toUpperCase();
}

/**
 * Generate a consistent background color from a string
 * Uses simple hash to pick from a palette
 */
function getColorFromName(name: string): string {
  const colors = [
    '#e57373', '#f06292', '#ba68c8', '#9575cd',
    '#7986cb', '#64b5f6', '#4fc3f7', '#4dd0e1',
    '#4db6ac', '#81c784', '#aed581', '#dce775',
    '#fff176', '#ffd54f', '#ffb74d', '#ff8a65',
  ];
  
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  return colors[Math.abs(hash) % colors.length];
}

/**
 * Get the proxied URL for an image
 * External URLs (http/https) are routed through our proxy to bypass hotlink protection.
 * Local URLs (/, data:, blob:) are returned as-is.
 */
function getProxiedSrc(src: string | undefined): string | undefined {
  if (!src) return undefined;
  
  // Local URLs - use directly
  if (src.startsWith('/') || src.startsWith('data:') || src.startsWith('blob:')) {
    return src;
  }
  
  // External URLs - proxy them
  if (src.startsWith('http://') || src.startsWith('https://')) {
    return `/ui/proxy/image?url=${encodeURIComponent(src)}`;
  }
  
  // Anything else - use as-is (relative paths, etc.)
  return src;
}

export function Image({
  src,
  alt,
  variant = 'thumbnail',
  size,
  fallback = 'none',
  name,
  className = '',
}: ImageProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  
  // Determine if we should show fallback
  const showFallback = !src || hasError;
  
  // Build data attributes for CSS hooks
  const dataProps: Record<string, string | undefined> = {
    'data-variant': variant,
  };
  if (size) dataProps['data-size'] = size;
  if (showFallback) dataProps['data-fallback'] = 'true';
  
  // Render initials fallback
  if (showFallback && fallback === 'initials' && name) {
    const initials = getInitials(name);
    const bgColor = getColorFromName(name);
    
    return (
      <div
        className={`image image--initials ${className}`.trim()}
        {...dataProps}
        style={{ backgroundColor: bgColor }}
        role="img"
        aria-label={alt || name}
      >
        <span className="image__initials">{initials}</span>
      </div>
    );
  }
  
  // Render icon fallback
  if (showFallback && fallback === 'icon') {
    return (
      <div
        className={`image image--icon-fallback ${className}`.trim()}
        {...dataProps}
        role="img"
        aria-label={alt || 'Image'}
      >
        <span className="image__icon">📷</span>
      </div>
    );
  }
  
  // Render nothing if no src and fallback is 'none'
  if (showFallback && fallback === 'none') {
    return null;
  }
  
  // Render actual image (external URLs are proxied)
  const proxiedSrc = getProxiedSrc(src);
  
  return (
    <img
      className={`image ${className}`.trim()}
      src={proxiedSrc}
      alt={alt || ''}
      {...dataProps}
      data-loaded={isLoaded || undefined}
      onError={() => setHasError(true)}
      onLoad={() => setIsLoaded(true)}
    />
  );
}

export default Image;
