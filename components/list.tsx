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
 * The framework (AppRenderer) handles loading item components and evaluating
 * template props. This component just renders what it's given.
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

import { useState, useRef, useEffect, Children, ReactNode, KeyboardEvent, useCallback } from 'react';

interface ListProps {
  /** Original data items (used for callbacks to identify which item was selected) */
  items?: Array<{ id?: string; [key: string]: unknown }>;
  /** Pre-rendered item components (from AppRenderer children pattern) */
  children?: ReactNode;
  /** Layout direction */
  layout?: 'vertical' | 'horizontal';
  /** Visual variant for different use cases */
  variant?: 'default' | 'chat' | 'cards';
  /** Show loading state */
  loading?: boolean;
  /** Error message to display */
  error?: string;
  /** Empty state message when no items */
  emptyMessage?: string;
  /** Fired when an item is clicked/selected */
  onSelect?: (item: unknown, index: number) => void;
  /** Fired when an item is double-clicked */
  onDoubleClick?: (item: unknown, index: number) => void;
  /** Accessibility label for the list */
  'aria-label'?: string;
}

export function List({
  items = [],
  children,
  layout = 'vertical',
  variant = 'default',
  loading = false,
  error,
  emptyMessage = 'No items',
  onSelect,
  onDoubleClick,
  'aria-label': ariaLabel = 'List',
}: ListProps) {
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const listRef = useRef<HTMLDivElement>(null);
  const childArray = Children.toArray(children);

  // Reset selection when items change
  useEffect(() => {
    setSelectedIndex(-1);
  }, [items.length]);

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
        setSelectedIndex(prev => {
          const next = prev < itemCount - 1 ? prev + 1 : prev;
          return next;
        });
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => {
          const next = prev > 0 ? prev - 1 : 0;
          return next;
        });
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

  // Loading state
  if (loading) {
    return (
      <div 
        className="list list--loading" 
        role="list" 
        aria-label={ariaLabel}
        aria-busy="true"
      >
        <div className="list-loading">
          <span className="list-loading-spinner" aria-hidden="true" />
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
