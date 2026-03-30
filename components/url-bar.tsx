/**
 * URL Bar Component
 * 
 * A browser-style location bar showing the current data source URL.
 * For entity apps, this shows:
 * - All sources: the graph API URL (e.g., localhost:3456/mem/tasks)
 * - Filtered to single source: the skill's web URL (e.g., https://app.todoist.com/app/today)
 * 
 * Features:
 * - Navigation buttons (back, forward, refresh)
 * - Globe (or loading) indicator in the bar
 * - Clickable URL that can be copied or opened externally
 * - Useful for developers to see/use the underlying API
 * 
 * @example Graph API URL (all sources):
 * ```yaml
 * toolbar:
 *   - component: url-bar
 *     props:
 *       webUrl: "http://localhost:3456/mem/tasks"
 * ```
 * 
 * @example Skill URL (filtered to single source):
 * ```yaml
 * toolbar:
 *   - component: url-bar
 *     props:
 *       skill: todoist
 *       webUrl: "https://app.todoist.com/app/today"
 * ```
 */

import React, { useState } from 'react';

interface UrlBarProps {
  /** Display mode: 'search' shows query, 'url' shows address */
  mode?: 'search' | 'url';
  /** The query or URL to display */
  value?: string;
  /** User-facing URL that can be copied/visited */
  webUrl?: string;
  /** Skill ID (reserved for future use; bar no longer shows a skill image) */
  skill?: string;
  /** Show loading spinner */
  loading?: boolean;
  /** Can navigate back in history */
  canGoBack?: boolean;
  /** Can navigate forward in history */
  canGoForward?: boolean;
  /** Callback when back button clicked */
  onBack?: () => void;
  /** Callback when forward button clicked */
  onForward?: () => void;
  /** Callback to refresh data (graph apps) */
  onRefresh?: () => void;
  /** Whether data is currently being refreshed */
  refreshing?: boolean;
  /** Whether data is from a fresh pull (vs cache) */
  isFresh?: boolean;
  /** When the data was last updated (for cache age) */
  lastUpdated?: Date | null;
}

/** Format a date as relative time (e.g., "5m ago", "2h ago") */
function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  return `${diffDay}d ago`;
}

// Simple SVG icons - inline to avoid external dependencies
const Icons = {
  back: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
      <path d="M11 2L5 8l6 6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  forward: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
      <path d="M5 2l6 6-6 6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  refresh: (
    <svg viewBox="0 0 24 24" width="14" height="14">
      <path fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.651 7.65a7.131 7.131 0 0 0-12.68 3.15M18.001 4v4h-4m-7.652 8.35a7.13 7.13 0 0 0 12.68-3.15M6 20v-4h4"/>
    </svg>
  ),
  stop: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  search: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
      <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="2" fill="none"/>
      <path d="M10 10l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),
  globe: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <ellipse cx="8" cy="8" rx="3" ry="6.5" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <path d="M1.5 8h13M2.5 4.5h11M2.5 11.5h11" stroke="currentColor" strokeWidth="1"/>
    </svg>
  ),
  loading: (
    <svg viewBox="0 0 16 16" width="14" height="14" className="url-bar-spinner">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.3"/>
      <path d="M8 2a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round"/>
    </svg>
  ),
  copy: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <rect x="5" y="5" width="8" height="9" rx="1" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <path d="M11 5V3a1 1 0 00-1-1H4a1 1 0 00-1 1v8a1 1 0 001 1h2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
    </svg>
  ),
  external: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <path d="M12 9v4H3V4h4M8 8l6-6M10 2h4v4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  check: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <path d="M3 8l4 4 6-8" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

export function UrlBar({
  mode = 'url',
  value = '',
  webUrl,
  skill,
  loading = false,
  canGoBack = false,
  canGoForward = false,
  onBack,
  onForward,
  onRefresh,
  refreshing = false,
  isFresh = false,
  lastUpdated,
}: UrlBarProps) {
  const [copied, setCopied] = useState(false);
  
  // Navigation is enabled when callbacks are provided and history exists
  const backEnabled = canGoBack && !!onBack;
  const forwardEnabled = canGoForward && !!onForward;

  // Display value: prefer webUrl, fall back to value
  const displayValue = webUrl || value;
  const isClickable = !!webUrl;

  // Cache age indicator
  // Show "Cached Xm ago" if not fresh and data is older than 1 minute
  const showCacheAge = !isFresh && lastUpdated && !refreshing;
  const cacheAgeText = lastUpdated ? formatTimeAgo(lastUpdated) : null;
  
  // Copy URL handler
  const handleCopy = async () => {
    if (!webUrl) return;
    try {
      await navigator.clipboard.writeText(webUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  
  // Open external URL handler
  const handleOpenExternal = () => {
    if (!webUrl) return;
    window.open(webUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="url-bar" data-mode={mode} data-loading={loading}>
      {/* Navigation buttons */}
      <div className="url-bar-nav">
        <button
          className="url-bar-nav-button"
          disabled={!backEnabled}
          onClick={backEnabled ? onBack : undefined}
          aria-label="Back"
          title={backEnabled ? "Go back in history" : "No previous history"}
        >
          {Icons.back}
        </button>
        <button
          className="url-bar-nav-button"
          disabled={!forwardEnabled}
          onClick={forwardEnabled ? onForward : undefined}
          aria-label="Forward"
          title={forwardEnabled ? "Go forward in history" : "At latest"}
        >
          {Icons.forward}
        </button>
        <button
          className="url-bar-nav-button"
          disabled={!onRefresh || refreshing}
          onClick={onRefresh}
          aria-label={refreshing ? "Refreshing" : "Refresh"}
          title={refreshing ? "Loading..." : (onRefresh ? "Refresh data from sources" : "Refresh (observation mode)")}
          data-refreshing={refreshing}
        >
          {refreshing ? Icons.loading : Icons.refresh}
        </button>
      </div>

      {/* URL field */}
      <div className="url-bar-field">
        {/* Source indicator: globe (skills no longer ship image icons) */}
        <span className="url-bar-icon" aria-hidden="true">
          {loading ? Icons.loading : Icons.globe}
        </span>

        {/* URL display - clickable */}
        {isClickable ? (
          <a
            className="url-bar-value url-bar-link"
            href={webUrl}
            target="_blank"
            rel="noopener noreferrer"
            title={`Open ${webUrl}`}
          >
            {displayValue}
          </a>
        ) : displayValue ? (
          <span className="url-bar-value" title={displayValue}>
            {displayValue}
          </span>
        ) : (
          <span className="url-bar-value url-bar-empty">
            {loading ? 'Loading...' : ''}
          </span>
        )}

        {/* Cache age indicator */}
        {showCacheAge && cacheAgeText && cacheAgeText !== 'just now' && (
          <span 
            className="url-bar-cache-age" 
            title={lastUpdated ? `Last updated: ${lastUpdated.toLocaleString()}` : undefined}
          >
            Cached {cacheAgeText}
          </span>
        )}
        
        {/* Action buttons - copy and external link */}
        {webUrl && (
          <div className="url-bar-actions">
            <button
              className="url-bar-action-button"
              onClick={handleCopy}
              aria-label={copied ? "Copied!" : "Copy URL"}
              title={copied ? "Copied!" : `Copy ${webUrl}`}
              data-copied={copied}
            >
              {copied ? Icons.check : Icons.copy}
            </button>
            <button
              className="url-bar-action-button"
              onClick={handleOpenExternal}
              aria-label="Open in browser"
              title={`Open ${webUrl}`}
            >
              {Icons.external}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default UrlBar;
