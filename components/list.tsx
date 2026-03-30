/**
 * List Primitive Component
 * 
 * A pure container component that wraps children with list behavior:
 * - Keyboard navigation (arrow keys, Enter)
 * - Selection state and visual feedback
 * - Click and double-click handling
 * - Loading and error states
 * - Full accessibility (ARIA roles, focus management)
 * 
 * @example
 * ```yaml
 * - component: list
 *   data:
 *     capability: web_search
 *   item_component: items/search-result
 *   item_props:
 *     title: "{{title}}"
 *     url: "{{url}}"
 * ```
 */

import React, { useState, useRef, useEffect, Children, ReactNode, KeyboardEvent, useCallback } from 'react';

// =============================================================================
// Types
// =============================================================================

export interface ListProps {
  /** Original data items (used for callbacks) */
  items?: Array<{ id?: string; [key: string]: unknown }>;
  /** Pre-rendered item components */
  children?: ReactNode;
  /** Layout direction */
  layout?: 'vertical' | 'horizontal';
  /** Visual variant */
  variant?: 'default' | 'chat' | 'cards' | 'sidebar';
  /** Show loading state */
  loading?: boolean;
  /** Error message */
  error?: string;
  /** Empty state message */
  emptyMessage?: string;
  /** Controlled selected index (when provided, component is controlled) */
  selectedIndex?: number;
  /** Callback when selection changes (for controlled mode) */
  onSelectedIndexChange?: (index: number) => void;
  /** Select handler (fires on Enter/click with item data) */
  onSelect?: (item: unknown, index: number) => void;
  /** Double-click handler */
  onDoubleClick?: (item: unknown, index: number) => void;
  /** Accessibility label */
  'aria-label'?: string;
}

// =============================================================================
// Component
// =============================================================================

export function List(props: ListProps) {
  // Apply defaults
  const {
    items = [],
    children,
    layout = 'vertical',
    variant = 'default',
    loading = false,
    error,
    emptyMessage = 'No items',
    selectedIndex: controlledIndex,
    onSelectedIndexChange,
    onSelect,
    onDoubleClick,
    'aria-label': ariaLabel = 'List',
  } = props;

  // Support both controlled and uncontrolled modes
  const isControlled = controlledIndex !== undefined;
  const [internalIndex, setInternalIndex] = useState(-1);
  const selectedIndex = isControlled ? controlledIndex : internalIndex;
  
  const setSelectedIndex = useCallback((indexOrUpdater: number | ((prev: number) => number)) => {
    const newIndex = typeof indexOrUpdater === 'function' 
      ? indexOrUpdater(selectedIndex) 
      : indexOrUpdater;
    
    if (isControlled) {
      onSelectedIndexChange?.(newIndex);
    } else {
      setInternalIndex(newIndex);
    }
  }, [isControlled, selectedIndex, onSelectedIndexChange]);

  const listRef = useRef<HTMLDivElement>(null);
  const childArray = Children.toArray(children);

  // Reset selection when items change (only in uncontrolled mode)
  useEffect(() => {
    if (!isControlled) {
      setInternalIndex(-1);
    }
  }, [items.length, isControlled]);

  // Scroll selected item into view
  useEffect(() => {
    if (selectedIndex >= 0 && listRef.current) {
      const selectedElement = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
      selectedElement?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedIndex]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const itemCount = childArray.length;
    if (itemCount === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => prev < itemCount - 1 ? prev + 1 : prev);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : 0);
        break;
      case 'Home':
        e.preventDefault();
        setSelectedIndex(0);
        break;
      case 'End':
        e.preventDefault();
        setSelectedIndex(itemCount - 1);
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < items.length) {
          onSelect?.(items[selectedIndex], selectedIndex);
        }
        break;
    }
  }, [childArray.length, items, selectedIndex, onSelect]);

  // Handle item click
  const handleItemClick = useCallback((index: number) => {
    setSelectedIndex(index);
    if (index < items.length) {
      onSelect?.(items[index], index);
    }
  }, [items, onSelect]);

  // Handle item double-click
  const handleItemDoubleClick = useCallback((index: number) => {
    if (index < items.length) {
      onDoubleClick?.(items[index], index);
    }
  }, [items, onDoubleClick]);

  // Loading state - show Mac OS 9 style indeterminate progress bar
  if (loading) {
    return (
      <div 
        className="list list--loading" 
        data-component="list"
        data-variant={variant}
        role="list" 
        aria-label={ariaLabel}
        aria-busy="true"
      >
        <div className="list-loading">
          <div className="progress-bar" role="progressbar" aria-label="Loading..." />
          <span className="list-loading-text">Loading...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div 
        className="list list--error" 
        data-component="list"
        data-variant={variant}
        role="alert" 
        aria-label={ariaLabel}
      >
        <div className="list-error">
          <span className="list-error-icon" aria-hidden="true">⚠</span>
          <span className="list-error-text">{error}</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (childArray.length === 0) {
    return (
      <div 
        className="list list--empty" 
        data-component="list"
        data-variant={variant}
        role="list" 
        aria-label={ariaLabel}
      >
        <div className="list-empty">
          <span className="list-empty-text">{emptyMessage}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={listRef}
      className="list"
      data-component="list"
      role="listbox"
      aria-label={ariaLabel}
      aria-activedescendant={selectedIndex >= 0 ? `list-item-${selectedIndex}` : undefined}
      data-layout={layout}
      data-variant={variant}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {childArray.map((child, index) => (
        <div
          key={items[index]?.id ?? index}
          id={`list-item-${index}`}
          className="list-item"
          data-component="list-item"
          role="option"
          aria-selected={index === selectedIndex}
          data-index={index}
          data-selected={index === selectedIndex}
          tabIndex={-1}
          onClick={() => handleItemClick(index)}
          onDoubleClick={() => handleItemDoubleClick(index)}
        >
          {child}
        </div>
      ))}
    </div>
  );
}

export default List;
