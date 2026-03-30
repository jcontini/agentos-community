/**
 * App Toolbar Component
 * 
 * Unified toolbar for auto-generated apps (Tasks, Messages, Calendar, etc.).
 * Combines navigation, connector info, and actions in one bar.
 * 
 * Layout: ◀ ▶ ↻  │  🔴 Todoist  │  2 min ago  │  ⧉  📋
 * 
 * Features:
 * - Navigation: back/forward through activity history
 * - Refresh: re-execute the current operation (future)
 * - Connector: skill monogram, name, and brand color
 * - Timestamp: relative time since activity
 * - Actions: open in browser, copy URL
 * 
 * @example
 * ```yaml
 * default_toolbar:
 *   default:
 *     - component: app-toolbar
 *       props:
 *         skill: "{{activity.skill}}"
 *         webUrl: "{{activity.web_url}}"
 *         timestamp: "{{activity.created_at}}"
 * ```
 */

import { useState, useEffect } from 'react';

interface AppToolbarProps {
  /** Skill ID (used for monogram + display name fallback) */
  skill?: string;
  /** Skill display name */
  skillName?: string;
  /** Skill brand color (hex, e.g., "#5E6AD2") */
  skillColor?: string;
  /** User-facing URL (for external link and copy) */
  webUrl?: string;
  /** Activity timestamp (ISO string) for "2 min ago" display */
  timestamp?: string;
  /** Show loading state */
  loading?: boolean;
  /** Can navigate back in history */
  canGoBack?: boolean;
  /** Can navigate forward in history */
  canGoForward?: boolean;
  /** Callback when back button clicked */
  onBack?: () => void;
  /** Callback when forward button clicked */
  onForward?: () => void;
  /** Callback when refresh button clicked (future) */
  onRefresh?: () => void;
}

// Simple SVG icons
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
  external: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
      <path d="M12 9v4H3V4h4M8 8l6-6M10 2h4v4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  copy: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
      <rect x="5" y="5" width="8" height="9" rx="1" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <path d="M11 5V3a1 1 0 00-1-1H4a1 1 0 00-1 1v8a1 1 0 001 1h2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
    </svg>
  ),
  check: (
    <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
      <path d="M3 8l4 4 6-8" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

/**
 * Format a timestamp as relative time (e.g., "2 min ago", "1 hour ago")
 */
function formatRelativeTime(timestamp: string | undefined): string {
  if (!timestamp) return '';
  
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);
  
  if (diffSec < 5) return 'just now';
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay === 1) return 'yesterday';
  return `${diffDay}d ago`;
}

export function AppToolbar({
  skill,
  skillName,
  skillColor,
  webUrl,
  timestamp,
  loading = false,
  canGoBack = false,
  canGoForward = false,
  onBack,
  onForward,
  onRefresh,
}: AppToolbarProps) {
  const [copied, setCopied] = useState(false);
  const [relativeTime, setRelativeTime] = useState(() => formatRelativeTime(timestamp));
  
  // Update relative time every minute
  useEffect(() => {
    setRelativeTime(formatRelativeTime(timestamp));
    const interval = setInterval(() => {
      setRelativeTime(formatRelativeTime(timestamp));
    }, 60000);
    return () => clearInterval(interval);
  }, [timestamp]);
  
  // Navigation handlers
  const backEnabled = canGoBack && !!onBack;
  const forwardEnabled = canGoForward && !!onForward;
  const refreshEnabled = !!onRefresh;
  
  const displayName = skillName || (skill ? skill.charAt(0).toUpperCase() + skill.slice(1) : '');
  
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

  const barStyle = skillColor ? { backgroundColor: skillColor } : undefined;

  return (
    <div className="app-toolbar-bar" style={barStyle}>
      {/* Navigation buttons */}
      <div className="app-toolbar-nav">
        <button
          className="app-toolbar-nav-button"
          disabled={!backEnabled}
          onClick={backEnabled ? onBack : undefined}
          aria-label="Back"
          title={backEnabled ? "Go back in history" : "No previous history"}
        >
          {Icons.back}
        </button>
        <button
          className="app-toolbar-nav-button"
          disabled={!forwardEnabled}
          onClick={forwardEnabled ? onForward : undefined}
          aria-label="Forward"
          title={forwardEnabled ? "Go forward in history" : "At latest"}
        >
          {Icons.forward}
        </button>
        <button
          className="app-toolbar-nav-button"
          disabled={!refreshEnabled}
          onClick={refreshEnabled ? onRefresh : undefined}
          aria-label="Refresh"
          title={refreshEnabled ? "Refresh data" : "Refresh (coming soon)"}
        >
          {Icons.refresh}
        </button>
      </div>
      
      {/* Connector info — monogram + name on theme chip */}
      {skill && (
        <div className="app-toolbar-connector">
          <span className="app-toolbar-skill-icon app-toolbar-skill-icon--monogram" aria-hidden>
            {skill.charAt(0).toUpperCase()}
          </span>
          <span className="app-toolbar-skill-name">{displayName}</span>
        </div>
      )}
      
      {/* Timestamp */}
      {relativeTime && (
        <span className="app-toolbar-timestamp" title={timestamp}>
          {relativeTime}
        </span>
      )}
      
      {/* Spacer */}
      <div className="app-toolbar-spacer" />
      
      {/* Action buttons */}
      <div className="app-toolbar-actions">
        {webUrl && (
          <>
            <button
              className="app-toolbar-action-button"
              onClick={handleOpenExternal}
              aria-label="Open in browser"
              title={`Open ${webUrl}`}
            >
              {Icons.external}
            </button>
            <button
              className="app-toolbar-action-button"
              onClick={handleCopy}
              aria-label={copied ? "Copied!" : "Copy URL"}
              title={copied ? "Copied!" : `Copy ${webUrl}`}
              data-copied={copied}
            >
              {copied ? Icons.check : Icons.copy}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default AppToolbar;
