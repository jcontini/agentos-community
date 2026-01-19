/**
 * Grid Primitive Component
 * 
 * A pure container component that arranges children in a grid layout:
 * - Configurable columns and gap
 * - Selection state and visual feedback
 * - Click and double-click handling
 * - Full accessibility (ARIA grid roles)
 * 
 * Follows the same children pattern as List - framework handles component
 * loading and prop evaluation, Grid just renders what it's given.
 * 
 * @example
 * ```yaml
 * - component: grid
 *   props:
 *     columns: 4
 *     gap: "16px"
 *   data:
 *     capability: gallery_list
 *   item_component: items/photo-card
 *   item_props:
 *     src: "{{thumbnail_url}}"
 *     title: "{{title}}"
 * ```
 */

import { useState, useRef, useEffect, Children, ReactNode, KeyboardEvent, useCallback } from 'react';

interface GridProps {
  /** Original data items (used for callbacks to identify which item was selected) */
  items?: Array<{ id?: string; [key: string]: unknown }>;
  /** Pre-rendered item components (from AppRenderer children pattern) */
  children?: ReactNode;
  /** Number of columns */
  columns?: number;
  /** Gap between items (CSS value) */
  gap?: string;
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
  /** Accessibility label for the grid */
  'aria-label'?: string;
}

export function Grid({
  items = [],
  children,
  columns = 4,
  gap = '16px',
  loading = false,
  error,
  emptyMessage = 'No items',
  onSelect,
  onDoubleClick,
  'aria-label': ariaLabel = 'Grid',
}: GridProps) {
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const gridRef = useRef<HTMLDivElement>(null);
  const childArray = Children.toArray(children);

  // Reset selection when items change
  useEffect(() => {
    setSelectedIndex(-1);
  }, [items.length]);

  // Keyboard navigation (2D grid navigation)
  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const itemCount = childArray.length;
    if (itemCount === 0) return;

    const currentRow = Math.floor(selectedIndex / columns);
    const currentCol = selectedIndex % columns;
    const totalRows = Math.ceil(itemCount / columns);

    switch (e.key) {
      case 'ArrowRight':
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, itemCount - 1));
        break;
      case 'ArrowLeft':
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'ArrowDown':
        e.preventDefault();
        if (currentRow < totalRows - 1) {
          const nextIndex = Math.min((currentRow + 1) * columns + currentCol, itemCount - 1);
          setSelectedIndex(nextIndex);
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (currentRow > 0) {
          const nextIndex = (currentRow - 1) * columns + currentCol;
          setSelectedIndex(nextIndex);
        }
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
  }, [childArray.length, columns, items, selectedIndex, onSelect]);

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
        className="grid grid--loading" 
        role="grid" 
        aria-label={ariaLabel}
        aria-busy="true"
      >
        <div className="grid-loading">
          <span className="grid-loading-spinner" aria-hidden="true" />
          <span className="grid-loading-text">Loading...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div 
        className="grid grid--error" 
        role="alert" 
        aria-label={ariaLabel}
      >
        <div className="grid-error">
          <span className="grid-error-icon" aria-hidden="true">⚠</span>
          <span className="grid-error-text">{error}</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (childArray.length === 0) {
    return (
      <div 
        className="grid grid--empty" 
        role="grid" 
        aria-label={ariaLabel}
      >
        <div className="grid-empty">
          <span className="grid-empty-text">{emptyMessage}</span>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={gridRef}
      className="grid"
      role="grid"
      aria-label={ariaLabel}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap,
      }}
    >
      {childArray.map((child, index) => (
        <div
          key={items[index]?.id ?? index}
          className="grid-item"
          role="gridcell"
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

export default Grid;
