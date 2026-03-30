/**
 * Entity Picker Component
 * 
 * A generic component for selecting one or more items from a collection.
 * Includes an inline entity-grid for display with data fetching, loading states,
 * and optional grouping.
 * 
 * Used for: theme picker, wallpaper picker, icon picker, file picker, etc.
 * 
 * CSS: Uses .entity-picker-* and .entity-grid-* classes from base.css
 * 
 * @example
 * ```yaml
 * # Pick from the graph
 * - component: entity-picker
 *   props:
 *     source: "/mem/themes"
 *     entity: theme
 *     selection: single
 * 
 * # Pick with grouping
 * - component: entity-picker
 *   props:
   *     source: "/mem/images?skill=system"
 *     entity: image
 *     groupBy: family
 *     selection: single
 * ```
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';

// =============================================================================
// Types (inline from entity-grid)
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

export interface ItemRenderProps {
  selected: boolean;
  focused: boolean;
  size: 'small' | 'medium' | 'large';
}

// =============================================================================
// Inline EntityGrid (to avoid import issues with embedded components)
// =============================================================================

const SIZE_CONFIGS = {
  small: { iconSize: 32, cellWidth: 70, cellHeight: 80 },
  medium: { iconSize: 48, cellWidth: 90, cellHeight: 100 },
  large: { iconSize: 64, cellWidth: 110, cellHeight: 120 },
};

function DefaultGridItem({ 
  item, 
  size,
  showLabel = true,
}: { 
  item: GridItem; 
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

interface InlineGridProps {
  items: GridItem[];
  size?: 'small' | 'medium' | 'large';
  selectable?: 'none' | 'single' | 'multiple';
  showLabels?: boolean;
  selected?: string | string[];
  onSelect?: (selected: string | string[]) => void;
  onActivate?: (item: GridItem) => void;
  renderItem?: (item: GridItem, props: ItemRenderProps) => React.ReactNode;
  className?: string;
  keyboard?: boolean;
}

function InlineGrid({
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
}: InlineGridProps) {
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  
  const selectedIds = Array.isArray(selected) ? selected : selected ? [selected] : [];
  
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
  
  const handleItemDoubleClick = useCallback((item: GridItem) => {
    onActivate?.(item);
  }, [onActivate]);
  
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
  
  useEffect(() => {
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

// =============================================================================
// Entity Picker Props
// =============================================================================

export interface EntityPickerProps {
  /**
   * Data source. Can be:
   * - Entity endpoint string (e.g., "/mem/themes", "/mem/images?skill=system")
   * - Entity type string (e.g., "theme", "image") - calls /mem/{entity}s
   * - Inline array of items
   */
  source: string | object[];
  
  /**
   * Entity type for schema-based rendering.
   * If source is a known entity type, this is inferred.
   * For API endpoints or inline data, specify to use display schema.
   */
  entity?: string;
  
  /**
   * Display mode - grid or list.
   * Default: inferred from entity schema's default_view, or 'grid'
   */
  display?: 'grid' | 'list';
  
  /** Grid/list item size */
  size?: 'small' | 'medium' | 'large';
  
  /** Show labels under items */
  showLabels?: boolean;
  
  /** Selection mode */
  selection?: 'single' | 'multiple' | 'none';
  
  /** Currently selected ID(s) */
  selected?: string | string[];
  
  /** Called when selection changes */
  onSelect?: (selected: string | string[]) => void;
  
  /** Called when item is activated (double-click/enter) */
  onActivate?: (item: GridItem) => void;
  
  /** Property to group items by (e.g., "family") */
  groupBy?: string;
  
  /** Custom item renderer */
  renderItem?: (item: GridItem, props: ItemRenderProps) => React.ReactNode;
  
  /** Additional class name */
  className?: string;
  
  /** Additional query params for API calls */
  params?: Record<string, string>;
  
  /** Transform API response to items array */
  transform?: (response: unknown) => object[];
  
  /** Label for empty state */
  emptyLabel?: string;
}

// =============================================================================
// Helpers
// =============================================================================

const KNOWN_ENTITIES = ['theme', 'photo', 'album', 'note', 'notebook', 'task', 'post'];

function isEntityType(source: string): boolean {
  return KNOWN_ENTITIES.includes(source);
}

function buildSourceUrl(source: string, params?: Record<string, string>): string {
  if (source.startsWith('/')) {
    const url = new URL(source, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }
    return url.pathname + url.search;
  }
  
  if (isEntityType(source)) {
    const entityPlural = source + 's';
    const url = new URL(`/mem/${entityPlural}`, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }
    return url.pathname + url.search;
  }
  
  return source;
}

/** Convert filename to display name (e.g., "10-5.png" → "10 5") */
function filenameToDisplayName(filename: string): string {
  const name = filename.replace(/\.[^.]+$/, ''); // Remove extension
  return name
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function normalizeItem(item: Record<string, unknown>, sourceUrl?: string): GridItem {
  // Determine the image property
  let iconSrc: string | undefined;
  if (item.preview) {
    iconSrc = String(item.preview);
  } else if (item.thumbnail) {
    iconSrc = String(item.thumbnail);
  } else if (item.icon) {
    iconSrc = String(item.icon);
  } else if (item.src) {
    iconSrc = String(item.src);
  } else if (item.path && typeof item.path === 'string') {
    // Wallpaper-style items with path property
    // Build URL based on source (wallpapers are served from /wallpapers/)
    if (sourceUrl?.includes('/wallpapers')) {
      iconSrc = `/wallpapers/${item.path}`;
    } else {
      iconSrc = String(item.path);
    }
  }
  
  // Determine the label property
  let name: string;
  if (item.name) {
    name = String(item.name);
  } else if (item.title) {
    name = String(item.title);
  } else if (item.filename && typeof item.filename === 'string') {
    // Wallpaper-style items with filename
    name = filenameToDisplayName(item.filename);
  } else {
    name = String(item.id || 'Untitled');
  }
  
  return {
    id: String(item.id || item.path || Math.random().toString(36).slice(2)),
    name,
    icon: iconSrc,
    thumbnail: iconSrc, // Use the same source for thumbnail
    preview: item.preview ? String(item.preview) : undefined,
    description: item.description ? String(item.description) : undefined,
    ...item,
  };
}

function defaultTransform(response: unknown, sourceUrl: string): object[] {
  if (Array.isArray(response)) {
    return response;
  }
  
  const resp = response as Record<string, unknown>;
  
  // Known API response shapes
  if (sourceUrl.includes('/themes') && resp.themes) {
    return resp.themes as object[];
  }
  if (sourceUrl.includes('/wallpapers') && resp.wallpapers) {
    return resp.wallpapers as object[];
  }
  if (resp.items) {
    return resp.items as object[];
  }
  if (resp.data) {
    return resp.data as object[];
  }
  if (resp.results) {
    return resp.results as object[];
  }
  
  const arrays = Object.values(resp).filter(Array.isArray);
  if (arrays.length === 1) {
    return arrays[0] as object[];
  }
  
  console.warn('EntityPicker: Could not extract items from response', response);
  return [];
}

interface GroupedSection {
  key: string;
  label: string;
  items: GridItem[];
}

function groupItems(items: GridItem[], groupBy: string): GroupedSection[] {
  const groups = new Map<string, GridItem[]>();
  
  items.forEach(item => {
    const groupValue = String(item[groupBy] || 'Other');
    if (!groups.has(groupValue)) {
      groups.set(groupValue, []);
    }
    groups.get(groupValue)!.push(item);
  });
  
  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, groupItems]) => ({
      key,
      label: key.charAt(0).toUpperCase() + key.slice(1),
      items: groupItems,
    }));
}

// =============================================================================
// Main Component
// =============================================================================

export function EntityPicker({
  source,
  entity,
  display = 'grid',
  size = 'medium',
  showLabels = true,
  selection = 'single',
  selected,
  onSelect,
  onActivate,
  groupBy,
  renderItem,
  className = '',
  params,
  transform,
  emptyLabel,
}: EntityPickerProps) {
  const [items, setItems] = useState<GridItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Determine entity type if not explicitly provided
  const entityType = useMemo(() => {
    if (entity) return entity;
    if (typeof source === 'string' && isEntityType(source)) return source;
    return undefined;
  }, [entity, source]);
  
  // Fetch items
  useEffect(() => {
    let cancelled = false;
    
    // Handle inline data
    if (Array.isArray(source)) {
      const normalized = source.map(item => 
        normalizeItem(item as Record<string, unknown>, undefined)
      );
      setItems(normalized);
      setLoading(false);
      return;
    }
    
    // Fetch from URL
    const url = buildSourceUrl(source, params);
    
    setLoading(true);
    setError(null);
    
    fetch(url)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load: ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        if (cancelled) return;
        
        const rawItems = transform ? transform(data) : defaultTransform(data, url);
        const normalized = rawItems.map(item => 
          normalizeItem(item as Record<string, unknown>, url)
        );
        
        setItems(normalized);
        setLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    
    return () => { cancelled = true; };
  }, [source, params, transform]);
  
  // Handle selection wrapper (for grouped display)
  const handleSelect = useCallback((selectedIds: string | string[]) => {
    onSelect?.(selectedIds);
  }, [onSelect]);
  
  // Grouped sections
  const sections = useMemo(() => {
    if (!groupBy) return null;
    return groupItems(items, groupBy);
  }, [items, groupBy]);
  
  // Loading state
  if (loading) {
    return (
      <div className={`entity-picker entity-picker--loading ${className}`}>
        <div className="entity-picker-loading">
          <div className="progress-bar" role="progressbar" aria-label="Loading..." />
          <span>Loading...</span>
        </div>
      </div>
    );
  }
  
  // Error state
  if (error) {
    return (
      <div className={`entity-picker entity-picker--error ${className}`}>
        <div className="entity-picker-error">
          <span className="entity-picker-error-icon">!</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }
  
  // Empty state
  if (items.length === 0) {
    return (
      <div className={`entity-picker entity-picker--empty ${className}`}>
        <div className="entity-picker-empty">
          <span>{emptyLabel || 'No items available'}</span>
        </div>
      </div>
    );
  }
  
  // Grouped display
  if (sections && sections.length > 1) {
    return (
      <div className={`entity-picker entity-picker--grouped ${className}`}>
        {sections.map(section => (
          <div key={section.key} className="entity-picker-group">
            <div className="entity-picker-group-header">
              {section.label}
            </div>
            <div className="entity-picker-group-content">
              {display === 'grid' ? (
                <InlineGrid
                  items={section.items}
                  size={size}
                  selectable={selection}
                  showLabels={showLabels}
                  selected={selected}
                  onSelect={handleSelect}
                  onActivate={onActivate}
                  renderItem={renderItem}
                />
              ) : (
                <div className="entity-picker-list-placeholder">
                  List view not yet implemented
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  }
  
  // Flat display (no grouping or single group)
  const displayItems = sections ? sections[0].items : items;
  
  return (
    <div className={`entity-picker ${className}`}>
      {display === 'grid' ? (
        <InlineGrid
          items={displayItems}
          size={size}
          selectable={selection}
          showLabels={showLabels}
          selected={selected}
          onSelect={handleSelect}
          onActivate={onActivate}
          renderItem={renderItem}
        />
      ) : (
        <div className="entity-picker-list-placeholder">
          List view not yet implemented
        </div>
      )}
    </div>
  );
}

export default EntityPicker;
