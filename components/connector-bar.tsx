/**
 * Account Bar Component (formerly Connector Bar)
 * 
 * Shows which skill/account provided the current data.
 * Lives inside the scroll viewport so it scrolls with content.
 * 
 * Features:
 * - Skill name on left (or entity name when showing all sources)
 * - Account dropdown on right for filtering
 * - Pin button to toggle sticky behavior
 * - When pinned, stays at top of scroll area
 * 
 * Multi-source mode:
 * - When unfiltered: shows entity name ("All Tasks") + "All accounts ▾"
 * - When filtered: shows filtered skill name/color + account dropdown
 * 
 * @example Single source:
 * ```tsx
 * <ConnectorBar 
 *   skill="linear" 
 *   account="Adavia" 
 *   skillName="Linear"
 *   skillColor="#5E6AD2"
 * />
 * ```
 * 
 * @example Multi-source with filter:
 * ```tsx
 * <ConnectorBar 
 *   connectors={[
 *     { skill: 'todoist', account: 'joe@work', name: 'Todoist', color: '#E44332' },
 *     { skill: 'linear', account: 'Adavia', name: 'Linear', color: '#5E6AD2' },
 *   ]}
 *   entityName="All Tasks"
 *   selectedFilter={null}
 *   onFilterChange={(skillId) => setFilter(skillId)}
 * />
 * ```
 */

import { useState, useEffect, useRef } from 'react';

// Inline SVG icons (no external dependencies)
const Icons = {
  pin: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <path d="M9.5 1.5L14.5 6.5L10 11L9 14L6.5 11.5L2 16L4.5 9.5L1 7L5 6L9.5 1.5Z" 
        stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  pinFilled: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <path d="M9.5 1.5L14.5 6.5L10 11L9 14L6.5 11.5L2 16L4.5 9.5L1 7L5 6L9.5 1.5Z" 
        fill="currentColor" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  chevronDown: (
    <svg viewBox="0 0 16 16" width="10" height="10">
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  check: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <path d="M3 8l4 4 6-8" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
};

interface Connector {
  skill: string;
  account: string;
  name?: string;
  color?: string;
  entities?: string[];
}

interface ConnectorBarProps {
  /** Skill ID (for single source, or when filtered) */
  skill?: string;
  /** Skill display name */
  skillName?: string;
  /** Skill brand color (hex, e.g., "#5E6AD2") */
  skillColor?: string;
  /** Account name (optional) */
  account?: string;
  /** Contextual info to show on the right (e.g., "r/programming", project name) */
  context?: string;
  /** Format hint for context display (e.g., "subreddit" adds r/ prefix) */
  contextType?: 'subreddit' | 'default';
  /** For aggregation: array of connectors when multiple sources */
  connectors?: Connector[];
  /** Entity display name for multi-source unfiltered view (e.g., "All Tasks") */
  entityName?: string;
  /** Currently selected filter (skill id, or null for "All") */
  selectedFilter?: string | null;
  /** Callback when filter changes via dropdown */
  onFilterChange?: (skillId: string | null) => void;
  /** Activity timestamp (ISO string) - no longer displayed, kept for compatibility */
  timestamp?: string;
}

/**
 * Format context based on type
 */
function formatContext(context?: string, contextType?: string, skill?: string): string | undefined {
  if (!context) return undefined;
  
  // Auto-detect subreddit format for Reddit
  if (contextType === 'subreddit' || skill === 'reddit') {
    return `r/${context}`;
  }
  
  return context;
}

export function ConnectorBar({
  skill,
  skillName,
  skillColor,
  account,
  context,
  contextType,
  connectors,
  entityName,
  selectedFilter,
  onFilterChange,
}: ConnectorBarProps) {
  const [isPinned, setIsPinned] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  // Close dropdown when clicking outside
  useEffect(() => {
    if (!dropdownOpen) return;
    
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);
  
  // Pin button JSX (inlined to avoid re-mount on re-render)
  const pinButton = (
    <button
      className={`connector-bar-pin ${isPinned ? 'connector-bar-pin--active' : ''}`}
      onClick={() => setIsPinned(!isPinned)}
      title={isPinned ? 'Unpin (scroll with content)' : 'Pin (stay at top)'}
      aria-pressed={isPinned}
    >
      {isPinned ? Icons.pinFilled : Icons.pin}
    </button>
  );
  
  // Multi-source mode: 2+ connectors with filter support
  const isMultiSource = connectors && connectors.length >= 2;
  
  if (isMultiSource) {
    // Find the selected connector (if filtered)
    const selectedConnector = selectedFilter 
      ? connectors.find(c => c.skill === selectedFilter)
      : null;
    
    // Determine display values based on filter state
    const displayName = selectedConnector 
      ? (selectedConnector.name || selectedConnector.skill.charAt(0).toUpperCase() + selectedConnector.skill.slice(1))
      : (entityName || 'All Sources');
    
    const displayAccount = selectedConnector
      ? (selectedConnector.account || selectedConnector.skill)
      : 'All accounts';
    
    const bgColor = selectedConnector?.color || '#666';
    const isFiltered = selectedFilter !== null;
    
    const handleSelect = (skillId: string | null) => {
      setDropdownOpen(false);
      if (onFilterChange) {
        onFilterChange(skillId);
      }
    };
    
    return (
      <div 
        className="connector-bar" 
        data-pinned={isPinned}
        data-multi-source={true}
        data-filtered={isFiltered}
        style={isFiltered ? { backgroundColor: bgColor, color: '#fff' } : undefined}
      >
        <div className="connector-bar-source">
          <span className="connector-bar-name">{displayName}</span>
          {pinButton}
        </div>
        
        <div className="connector-bar-right" ref={dropdownRef}>
          <button
            className="connector-bar-dropdown-trigger"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            aria-expanded={dropdownOpen}
            aria-haspopup="listbox"
          >
            <span>{displayAccount}</span>
            {Icons.chevronDown}
          </button>
          
          {dropdownOpen && (
            <div className="connector-bar-dropdown" role="listbox">
              {/* All option */}
              <button
                className="connector-bar-dropdown-item"
                data-selected={selectedFilter === null}
                onClick={() => handleSelect(null)}
                role="option"
                aria-selected={selectedFilter === null}
              >
                {selectedFilter === null && <span className="connector-bar-dropdown-check">{Icons.check}</span>}
                <span>All ({connectors.length})</span>
              </button>
              
              <div className="connector-bar-dropdown-divider" />
              
              {/* Connector options */}
              {connectors.map((connector) => (
                <button
                  key={connector.skill}
                  className="connector-bar-dropdown-item"
                  data-selected={selectedFilter === connector.skill}
                  onClick={() => handleSelect(connector.skill)}
                  role="option"
                  aria-selected={selectedFilter === connector.skill}
                >
                  {selectedFilter === connector.skill && (
                    <span className="connector-bar-dropdown-check">{Icons.check}</span>
                  )}
                  <span className="connector-bar-dropdown-icon connector-bar-dropdown-icon--monogram" aria-hidden>
                    {connector.skill.charAt(0).toUpperCase()}
                  </span>
                  <span>{connector.name || connector.skill}</span>
                  {connector.account && connector.account.toLowerCase() !== connector.skill.toLowerCase() && (
                    <span className="connector-bar-dropdown-account">{connector.account}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }
  
  // Single source mode (connectors array with 1 item, or skill prop)
  if (connectors && connectors.length === 1) {
    const connector = connectors[0];
    const singleSkillName = connector.name || connector.skill.charAt(0).toUpperCase() + connector.skill.slice(1);
    const singleSkillColor = connector.color || '#666';
    
    return (
      <div className="connector-bar" data-pinned={isPinned} style={{ backgroundColor: singleSkillColor, color: '#fff' }}>
        <div className="connector-bar-source">
          <span className="connector-bar-name">{singleSkillName}</span>
          {pinButton}
        </div>
        <div className="connector-bar-right">
          {connector.account && connector.account.toLowerCase() !== connector.skill.toLowerCase() && (
            <span className="connector-bar-context">{connector.account}</span>
          )}
        </div>
      </div>
    );
  }
  
  if (!skill) return null;
  const displayName = skillName || skill.charAt(0).toUpperCase() + skill.slice(1);
  const formattedContext = formatContext(context, contextType, skill);
  
  return (
    <div 
      className="connector-bar"
      data-pinned={isPinned}
      style={{ 
        backgroundColor: skillColor || '#666',
        color: '#fff',
      }}
    >
      <div className="connector-bar-source">
        <span className="connector-bar-name">{displayName}</span>
        {pinButton}
      </div>
      
      {/* Right side: context or account */}
      <div className="connector-bar-right">
        {(formattedContext || account) && (
          <span className="connector-bar-context">{formattedContext || account}</span>
        )}
      </div>
    </div>
  );
}

export default ConnectorBar;
