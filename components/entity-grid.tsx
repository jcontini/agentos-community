/**
 * Entity Grid Component
 * 
 * A generic grid layout for displaying entities as icons/thumbnails.
 * Used for: desktop icons, theme picker, wallpaper picker, photo albums, file browser.
 * 
 * CSS: Uses .entity-grid-* classes from base.css
 * 
 * @example
 * ```yaml
 * - component: entity-grid
 *   props:
 *     items: "{{response}}"
 *     size: medium
 *     selectable: single
 *     showLabels: true
 * ```
 */

import React, { useState, useCallback } from 'react';

// =============================================================================
// Types
// =============================================================================

export interface GridItem {
  /** Unique identifier */
  id: string;
  /** Display name/label */
  name: string;
  /** Icon or image URL */
  icon?: string;
  /** Optional thumbnail URL (for photos) */
  thumbnail?: string;
  /** Optional preview image (for themes) */
  preview?: string;
  /** Optional description */
  description?: string;
  /** Any additional data */
  [key: string]: unknown;
}

export interface EntityGridProps {
  /** Items to display in the grid */
  items: GridItem[];
  /** Icon/thumbnail size */
  size?: 'small' | 'medium' | 'large';
  /** Selection mode */
  selectable?: 'none' | 'single' | 'multiple';
  /** Show labels under icons */
  showLabels?: boolean;
  /** Currently selected item ID(s) */
  selected?: string | string[];
  /** Callback when selection changes */
  onSelect?: (selected: string | string[]) => void;
  /** Callback when item is activated (double-click or enter) */
  onActivate?: (item: GridItem) => void;
  /** Custom item renderer (optional) */
  renderItem?: (item: GridItem, props: ItemRenderProps) => React.ReactNode;
  /** Additional CSS class */
  className?: string;
  /** Enable keyboard navigation */
  keyboard?: boolean;
}

export interface ItemRenderProps {
  selected: boolean;
  focused: boolean;
  size: 'small' | 'medium' | 'large';
}

// =============================================================================
// Size configurations
// =============================================================================

const SIZE_CONFIGS = {
  small: { iconSize: 32, cellWidth: 70, cellHeight: 80 },
  medium: { iconSize: 48, cellWidth: 90, cellHeight: 100 },
  large: { iconSize: 64, cellWidth: 110, cellHeight: 120 },
};

// =============================================================================
// Default Item Renderer
// =============================================================================

function DefaultGridItem({ 
  item, 
  selected, 
  size,
  showLabel = true,
}: { 
  item: GridItem; 
  selected: boolean;
  size: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}) {
  const [iconFailed, setIconFailed] = useState(false);
  const config = SIZE_CONFIGS[size];
  
  // Determine which image to show (thumbnail > preview > icon)
  const imageSrc = item.thumbnail || item.preview || item.icon;
  
  return (
    <div 
      className="entity-grid-item-content"
      style={{ '--icon-size': `${config.iconSize}px` } as React.CSSProperties}
    >
      {imageSrc && !iconFailed ? (
        <img 
          src={imageSrc}
          alt=""
          className="entity-grid-item-icon"
          draggable={false}
          onError={() => setIconFailed(true)}
        />
      ) : (
        <div className="entity-grid-item-icon entity-grid-item-icon--fallback">
          <span>{item.name.charAt(0).toUpperCase()}</span>
        </div>
      )}
      {showLabel && (
        <span className="entity-grid-item-label">{item.name}</span>
      )}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function EntityGrid({
  items,
  size = 'medium',
  selectable = 'single',
  showLabels = true,
  selected,
  onSelect,
  onActivate,
  renderItem,
  className = '',
  keyboard = true,
}: EntityGridProps) {
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  
  // Normalize selected to array for internal use
  const selectedIds = Array.isArray(selected) ? selected : selected ? [selected] : [];
  
  // Handle item click
  const handleItemClick = useCallback((item: GridItem, index: number) => {
    if (selectable === 'none') return;
    
    setFocusedIndex(index);
    
    if (selectable === 'single') {
      onSelect?.(item.id);
    } else if (selectable === 'multiple') {
      const isSelected = selectedIds.includes(item.id);
      if (isSelected) {
        onSelect?.(selectedIds.filter(id => id !== item.id));
      } else {
        onSelect?.([...selectedIds, item.id]);
      }
    }
  }, [selectable, selectedIds, onSelect]);
  
  // Handle item double-click (activate)
  const handleItemDoubleClick = useCallback((item: GridItem) => {
    onActivate?.(item);
  }, [onActivate]);
  
  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!keyboard || items.length === 0) return;
    
    const cols = Math.floor((e.currentTarget as HTMLElement).clientWidth / SIZE_CONFIGS[size].cellWidth);
    
    switch (e.key) {
      case 'ArrowRight':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + 1, items.length - 1));
        break;
      case 'ArrowLeft':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + cols, items.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - cols, 0));
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < items.length) {
          const item = items[focusedIndex];
          if (e.key === 'Enter') {
            onActivate?.(item);
          } else {
            handleItemClick(item, focusedIndex);
          }
        }
        break;
      case 'Home':
        e.preventDefault();
        setFocusedIndex(0);
        break;
      case 'End':
        e.preventDefault();
        setFocusedIndex(items.length - 1);
        break;
    }
  }, [keyboard, items, size, focusedIndex, onActivate, handleItemClick]);
  
  // Select focused item when focus changes
  React.useEffect(() => {
    if (focusedIndex >= 0 && focusedIndex < items.length && selectable !== 'none') {
      const item = items[focusedIndex];
      if (selectable === 'single') {
        onSelect?.(item.id);
      }
    }
  }, [focusedIndex, items, selectable, onSelect]);
  
  const config = SIZE_CONFIGS[size];
  
  return (
    <div
      className={`entity-grid ${className}`}
      data-size={size}
      data-selectable={selectable}
      tabIndex={keyboard ? 0 : undefined}
      onKeyDown={keyboard ? handleKeyDown : undefined}
      role="grid"
      aria-label="Grid"
      style={{
        '--cell-width': `${config.cellWidth}px`,
        '--cell-height': `${config.cellHeight}px`,
      } as React.CSSProperties}
    >
      {items.map((item, index) => {
        const isSelected = selectedIds.includes(item.id);
        const isFocused = focusedIndex === index;
        
        return (
          <div
            key={item.id}
            className="entity-grid-item"
            data-selected={isSelected}
            data-focused={isFocused}
            role="gridcell"
            aria-selected={isSelected}
            onClick={() => handleItemClick(item, index)}
            onDoubleClick={() => handleItemDoubleClick(item)}
          >
            {renderItem ? (
              renderItem(item, { selected: isSelected, focused: isFocused, size })
            ) : (
              <DefaultGridItem 
                item={item} 
                selected={isSelected}
                size={size}
                showLabel={showLabels}
              />
            )}
          </div>
        );
      })}
      
      {items.length === 0 && (
        <div className="entity-grid-empty">
          No items
        </div>
      )}
    </div>
  );
}

export default EntityGrid;
