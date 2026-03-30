/**
 * Activity Footer Component
 * 
 * Displays attribution and metadata for an activity: source skill,
 * result count, and duration. Shows users where data came from.
 * 
 * @example
 * ```yaml
 * footer:
 *   count: "{{activity.response.length}}"
 *   source: "{{activity.connector}}"
 *   duration: "{{activity.duration_ms}}"
 * ```
 */

import React from 'react';

interface ActivityFooterProps {
  /** Source skill/connector name (e.g., 'exa', 'firecrawl') */
  source?: string;
  /** Source skill icon URL */
  sourceIcon?: string;
  /** Number of results */
  count?: number;
  /** Duration in milliseconds */
  duration?: number;
  /** Custom label for the count (default: "results") */
  countLabel?: string;
}

export function ActivityFooter({
  source,
  sourceIcon,
  count,
  duration,
  countLabel = 'results',
}: ActivityFooterProps) {
  // Format duration nicely
  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  // Don't render if no content
  if (!source && count === undefined && duration === undefined) {
    return null;
  }

  return (
    <div className="activity-footer">
      <div className="activity-footer-left">
        {source && (
          <span className="activity-footer-source">
            {sourceIcon && (
              <img 
                src={sourceIcon} 
                alt="" 
                className="activity-footer-source-icon"
              />
            )}
            <span className="activity-footer-source-label">via</span>
            <span className="activity-footer-source-name">{source}</span>
          </span>
        )}
      </div>

      <div className="activity-footer-right">
        {count !== undefined && (
          <span className="activity-footer-count">
            <span className="activity-footer-count-number">{count}</span>
            {' '}{countLabel}
          </span>
        )}

        {duration !== undefined && (
          <span className="activity-footer-duration">
            {formatDuration(duration)}
          </span>
        )}
      </div>
    </div>
  );
}

export default ActivityFooter;
