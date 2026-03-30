/**
 * Entity List Component
 * 
 * Generic list view that renders items based on entity type.
 * Fetches entity schema to get display hints for rich rendering:
 * 
 * - Images/thumbnails from display.image (proxy + initials fallback)
 * - Description snippets from display.description
 * - Smart formatting: duration, counts, relative time
 * - Schema-driven sorting from display.sort
 * 
 * This component replaces per-entity custom list views (video-search-result,
 * group-item, post-item, search-result) with a single generic renderer
 * that reads the entity schema and renders accordingly.
 * 
 * Styles defined in base.css (.entity-list-*)
 * 
 * @example
 * ```yaml
 * - component: entity-list
 *   props:
 *     entity: "{{entity}}"
 *     items: "{{entities}}"
 *     pending: "{{loading}}"
 * ```
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  getEntitySchema,
  getNestedValue,
  getProxiedSrc,
  extractImageUrl,
  getInitials,
  getColorFromString,
  inferImageVariant,
  formatDuration,
  formatCount,
  formatRelativeTime,
  formatValue,
} from '/ui/lib/utils.js';

interface EntityListProps {
  /** Entity type (e.g., 'task', 'post', 'message') */
  entity?: string;
  /** Array of items to display */
  items?: Array<Record<string, unknown>>;
  /** Whether data is still loading */
  pending?: boolean;
  /** Error message if request failed */
  error?: string;
}

/**
 * Entity schema display hints (fetched from API)
 */
interface DisplayHints {
  primary?: string;
  secondary?: string;
  description?: string;
  image?: string;
  status?: string;
  icon?: string;
  sort?: Array<{
    field: string;
    order?: string;
    completed_last?: boolean;
    null_last?: boolean;
  }>;
  /** Metadata fields to show inline (e.g., ["duration_ms", "view_count", "published_at"]) */
  meta?: string[];
  /** Field containing embeddable URL */
  embed?: string;
}

/**
 * Default display hints when schema not available.
 */
const DEFAULT_HINTS: DisplayHints = { primary: 'title' };

// Utilities imported from /lib/utils.js

// ─── Sub-components ─────────────────────────────────────────────────────────────

/**
 * Parse text and render markdown links: [text](url)
 */
function renderTextWithLinks(text: string): React.ReactNode {
  const markdownLinkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  markdownLinkRegex.lastIndex = 0;

  while ((match = markdownLinkRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <a
        key={match.index}
        href={match[2]}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="entity-list-item-link"
        title={match[2]}
      >
        {match[1]}
      </a>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length === 0 ? text : <>{parts}</>;
}

/**
 * Priority badge (P1-P4)
 */
function PriorityBadge({ priority }: { priority: number }) {
  return <span data-component="badge" data-priority={priority}>P{priority}</span>;
}

/**
 * Image with proxy, error handling, and initials fallback.
 * Variant determines size/shape: 'thumbnail' (wide rect) or 'avatar' (small circle).
 */
function ItemImage({
  src,
  alt,
  variant,
}: {
  src?: string;
  alt: string;
  variant: 'thumbnail' | 'avatar';
}) {
  const [error, setError] = useState(false);
  const proxied = getProxiedSrc(src);

  if (proxied && !error) {
    return (
      <img
        className={`entity-list-item-image entity-list-item-image--${variant}`}
        src={proxied}
        alt=""
        onError={() => setError(true)}
        loading="lazy"
      />
    );
  }

  // Initials fallback
  return (
    <div
      className={`entity-list-item-initials entity-list-item-initials--${variant}`}
      style={{ backgroundColor: getColorFromString(alt) }}
      role="img"
      aria-hidden="true"
    >
      {getInitials(alt)}
    </div>
  );
}

// ─── Filtering ──────────────────────────────────────────────────────────────────

/** Property definition from entity schema */
interface PropertyDef {
  type: string | null;
  description?: string;
  enum?: string[] | null;
  required?: boolean;
  references?: string | null;
}

/** Active filter state */
interface FilterState {
  search: string;
  enums: Record<string, string | null>;
}

const EMPTY_FILTERS: FilterState = { search: '', enums: {} };

const FILTER_STORAGE_PREFIX = 'agentos-filters:';

/** Save filter state to localStorage for an entity type (enum filters only, not text search) */
function saveFilters(entity: string, filters: FilterState): void {
  const key = FILTER_STORAGE_PREFIX + entity;
  const hasEnumFilters = Object.values(filters.enums).some(v => v !== null && v !== undefined);
  if (!hasEnumFilters) {
    try { localStorage.removeItem(key); } catch {}
    return;
  }
  try {
    localStorage.setItem(key, JSON.stringify({ enums: filters.enums }));
  } catch {}
}

/** Load persisted filter state from localStorage for an entity type */
function loadFilters(entity: string): FilterState {
  const key = FILTER_STORAGE_PREFIX + entity;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return EMPTY_FILTERS;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.enums) {
      return { search: '', enums: parsed.enums };
    }
  } catch {}
  return EMPTY_FILTERS;
}

const INTERNAL_FIELDS = new Set([
  'id', 'created_at', 'updated_at', '_entity_id', '_labels',
  'skill', 'account',
]);

const FilterIcons = {
  search: (
    <svg viewBox="0 0 16 16" width="12" height="12">
      <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <path d="M10 10l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  clear: (
    <svg viewBox="0 0 16 16" width="10" height="10">
      <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
};

/** Format enum value: snake_case → Title Case */
function formatEnumLabel(value: string): string {
  return value
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/** Check if an item matches a text search query */
function matchesTextSearch(item: Record<string, unknown>, query: string): boolean {
  for (const [key, value] of Object.entries(item)) {
    if (key.startsWith('_') || key === 'skill' || key === 'account') continue;
    if (typeof value === 'string' && value.toLowerCase().includes(query)) return true;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      if (matchesTextSearch(value as Record<string, unknown>, query)) return true;
    }
  }
  return false;
}

/** Get value from item, checking top-level and nested data.* */
function getFilterValue(item: Record<string, unknown>, field: string): unknown {
  if (field in item) return item[field];
  const data = item.data as Record<string, unknown> | undefined;
  if (data && typeof data === 'object' && field in data) return data[field];
  if (field.includes('.')) {
    return field.split('.').reduce((acc: unknown, key) => {
      if (acc && typeof acc === 'object') return (acc as Record<string, unknown>)[key];
      return undefined;
    }, item);
  }
  return undefined;
}

/** Apply filter state to items */
function applyFilters(
  items: Array<Record<string, unknown>>,
  filters: FilterState,
): Array<Record<string, unknown>> {
  let result = items;
  if (filters.search) {
    const q = filters.search.toLowerCase();
    result = result.filter(item => matchesTextSearch(item, q));
  }
  for (const [field, value] of Object.entries(filters.enums)) {
    if (value === null || value === undefined) continue;
    result = result.filter(item => {
      const v = getFilterValue(item, field);
      return v !== undefined && String(v) === value;
    });
  }
  return result;
}

/** Determine filterable enum fields from schema properties */
function getEnumFields(properties?: Record<string, PropertyDef>): Array<[string, PropertyDef]> {
  if (!properties) return [];
  const result: Array<[string, PropertyDef]> = [];
  for (const [name, prop] of Object.entries(properties)) {
    if (INTERNAL_FIELDS.has(name)) continue;
    if (!prop.type || prop.references) continue;
    if (prop.enum && prop.enum.length > 0) {
      result.push([name, prop]);
    }
  }
  return result;
}

/** Inline filter bar rendered within entity-list */
function FilterBar({
  properties,
  filters,
  onFilter,
  totalCount,
  filteredCount,
}: {
  properties?: Record<string, PropertyDef>;
  filters: FilterState;
  onFilter: (filters: FilterState) => void;
  totalCount: number;
  filteredCount: number;
}) {
  const searchRef = useRef<HTMLInputElement>(null);
  const enumFields = getEnumFields(properties);
  const hasActiveFilters = filters.search.length > 0 ||
    Object.values(filters.enums).some(v => v !== null && v !== undefined);
  const isFiltered = filteredCount < totalCount;

  return (
    <div className="entity-filter-bar" data-active={hasActiveFilters}>
      <div className="entity-filter-bar-search">
        <span className="entity-filter-bar-search-icon">{FilterIcons.search}</span>
        <input
          ref={searchRef}
          type="text"
          className="entity-filter-bar-search-input"
          placeholder="Filter..."
          value={filters.search}
          onChange={(e) => onFilter({ ...filters, search: e.target.value })}
          spellCheck={false}
          autoComplete="off"
        />
        {filters.search && (
          <button
            className="entity-filter-bar-clear-btn"
            onClick={() => { onFilter({ ...filters, search: '' }); searchRef.current?.focus(); }}
            aria-label="Clear search"
          >
            {FilterIcons.clear}
          </button>
        )}
      </div>

      {enumFields.map(([name, prop]) => (
        <div key={name} className="entity-filter-bar-enum">
          <select
            className="entity-filter-bar-select"
            value={filters.enums[name] ?? ''}
            onChange={(e) => onFilter({
              ...filters,
              enums: { ...filters.enums, [name]: e.target.value || null },
            })}
          >
            <option value="">
              {prop.description || formatEnumLabel(name)}
            </option>
            {prop.enum!.map((val) => (
              <option key={val} value={val}>{formatEnumLabel(val)}</option>
            ))}
          </select>
        </div>
      ))}

      {hasActiveFilters && (
        <div className="entity-filter-bar-status">
          {isFiltered && (
            <span className="entity-filter-bar-count">
              {filteredCount}/{totalCount}
            </span>
          )}
          <button
            className="entity-filter-bar-clear-all"
            onClick={() => onFilter(EMPTY_FILTERS)}
            aria-label="Clear all filters"
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}

// ─── List Item ──────────────────────────────────────────────────────────────────

function EntityListItem({
  item,
  hints,
  showCheckbox,
}: {
  item: Record<string, unknown>;
  hints: DisplayHints;
  showCheckbox?: boolean;
}) {
  // Resolve display values from schema hints
  const primaryValue = getNestedValue(item, hints.primary || 'title');
  const secondaryValue = hints.secondary ? getNestedValue(item, hints.secondary) : undefined;
  const descriptionRaw = hints.description ? getNestedValue(item, hints.description) : undefined;
  const imageRaw = hints.image ? getNestedValue(item, hints.image) : undefined;

  // Extract concrete values
  const primaryText = primaryValue ? String(primaryValue) : 'Untitled';
  const secondaryText = secondaryValue ? formatValue(secondaryValue, hints.secondary) : undefined;
  const descriptionText = descriptionRaw ? String(descriptionRaw) : undefined;
  const imageUrl = extractImageUrl(imageRaw);

  // Resolve meta fields (inline metadata like duration, view count, date)
  const metaParts: string[] = [];
  if (hints.meta) {
    for (const field of hints.meta) {
      const val = getNestedValue(item, field);
      if (val !== undefined && val !== null) {
        const formatted = formatValue(val, field);
        if (formatted) metaParts.push(formatted);
      }
    }
  }

  const priority = (item.priority ?? (item.data as Record<string, unknown>)?.priority) as number | undefined;
  // Use the schema's status path to resolve completed state (e.g., 'data.completed')
  const statusValue = hints.status ? getNestedValue(item, hints.status) : undefined;
  const completed = typeof statusValue === 'boolean' ? statusValue : undefined;
  const url = item.url as string | undefined;

  const hasImage = Boolean(hints.image);
  const imageVariant = inferImageVariant(hints.image);

  // Don't show description if it duplicates primary or secondary
  const showDescription = descriptionText
    && descriptionText !== primaryText
    && descriptionText !== secondaryText;

  // CSS classes
  const itemClasses = [
    'entity-list-item',
    url ? 'entity-list-item--clickable' : '',
    hasImage ? 'entity-list-item--has-image' : '',
  ].filter(Boolean).join(' ');

  const primaryClass = `entity-list-item-primary${completed ? ' entity-list-item-primary--completed' : ''}`;
  const checkboxClass = `entity-list-item-checkbox${completed ? ' entity-list-item-checkbox--checked' : ''}`;

  return (
    <div
      className={itemClasses}
      onClick={() => url && window.open(url, '_blank')}
    >
      {/* Checkbox (task-like entities with display.status) */}
      {showCheckbox && (
        <span className={checkboxClass}>
          {completed && (
            <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
              <path d="M2 6L5 9L10 3" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </span>
      )}

      {/* Image / Initials fallback */}
      {hasImage && (
        <ItemImage
          src={imageUrl}
          alt={primaryText}
          variant={imageVariant}
        />
      )}

      {/* Content */}
      <div className="entity-list-item-content">
        <div className={primaryClass}>
          {renderTextWithLinks(primaryText)}
        </div>

        {(secondaryText || metaParts.length > 0) && (
          <div className="entity-list-item-secondary">
            {secondaryText}
            {secondaryText && metaParts.length > 0 && ' · '}
            {metaParts.join(' · ')}
          </div>
        )}

        {showDescription && (
          <div className="entity-list-item-description">
            {descriptionText}
          </div>
        )}
      </div>

      {/* Badges */}
      <div className="entity-list-item-badges">
        {priority && priority >= 1 && priority <= 4 && (
          <PriorityBadge priority={priority} />
        )}
      </div>
    </div>
  );
}

// ─── Sorting ────────────────────────────────────────────────────────────────────

/**
 * Sort items based on schema-defined sort rules.
 * Supports: nested field paths, completed_last, null_last, asc/desc order.
 */
function sortItems(
  items: Array<Record<string, unknown>>,
  sortRules?: DisplayHints['sort']
): Array<Record<string, unknown>> {
  if (!sortRules || sortRules.length === 0) return items;

  return [...items].sort((a, b) => {
    for (const rule of sortRules) {
      const aVal = getNestedValue(a, rule.field);
      const bVal = getNestedValue(b, rule.field);

      // completed_last: push completed items to bottom
      if (rule.completed_last) {
        if (aVal && !bVal) return 1;
        if (!aVal && bVal) return -1;
        continue;
      }

      const order = rule.order === 'desc' ? -1 : 1;

      // Null handling
      const aNull = aVal === undefined || aVal === null;
      const bNull = bVal === undefined || bVal === null;
      if (aNull && bNull) continue;
      if (aNull) return rule.null_last ? 1 : -1;
      if (bNull) return rule.null_last ? -1 : 1;

      // Numeric comparison
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        if (aVal !== bVal) return (aVal - bVal) * order;
      }
      // String comparison
      else if (typeof aVal === 'string' && typeof bVal === 'string') {
        if (rule.field.includes('date') || rule.field.includes('_at')) {
          const aTime = new Date(aVal).getTime();
          const bTime = new Date(bVal).getTime();
          if (!isNaN(aTime) && !isNaN(bTime) && aTime !== bTime) {
            return (aTime - bTime) * order;
          }
        } else {
          const cmp = aVal.localeCompare(bVal);
          if (cmp !== 0) return cmp * order;
        }
      }
    }
    return 0;
  });
}

// ─── Main Component ─────────────────────────────────────────────────────────────

export function EntityList({
  entity = 'item',
  items,
  pending = false,
  error,
}: EntityListProps) {
  const [schema, setSchema] = useState<{ display?: DisplayHints; properties?: Record<string, PropertyDef> } | null>(null);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);

  useEffect(() => {
    if (!entity || entity === 'item') return;
    getEntitySchema(entity).then(setSchema);
  }, [entity]);

  // Load persisted filters when entity type changes
  useEffect(() => {
    setFilters(entity ? loadFilters(entity) : EMPTY_FILTERS);
  }, [entity]);

  // Wrap setFilters to persist enum filter preferences
  const updateFilters = useCallback((newFilters: FilterState) => {
    setFilters(newFilters);
    if (entity) saveFilters(entity, newFilters);
  }, [entity]);

  const hints: DisplayHints = schema?.display || DEFAULT_HINTS;

  // Normalize items: handle both arrays and { data: [...] } response wrapper
  const safeItems = Array.isArray(items)
    ? items
    : (items && typeof items === 'object' && Array.isArray((items as Record<string, unknown>).data))
      ? (items as Record<string, unknown>).data as Array<Record<string, unknown>>
      : [];

  // Apply filters → sort → render
  const filteredItems = applyFilters(safeItems, filters);
  const sortedItems = filteredItems.length > 0 ? sortItems(filteredItems, hints.sort) : [];

  // Fallback field detection: if the schema's primary field doesn't exist in data,
  // try common alternatives
  const effectiveHints = { ...hints };
  if (sortedItems.length > 0) {
    const sample = sortedItems[0];
    if (!getNestedValue(sample, effectiveHints.primary || 'title')) {
      if (sample.name) effectiveHints.primary = 'name';
      else if (sample.content) effectiveHints.primary = 'content';
      else if (sample.id) effectiveHints.primary = 'id';
    }
  }

  const showCheckbox = Boolean(effectiveHints.status);
  const showFilterBar = safeItems.length > 0 && schema?.properties;

  // Loading state
  if (pending) {
    return (
      <div className="entity-list">
        <div className="app-view-loading">
          <div className="progress-bar" />
          <span className="app-view-loading-text">Loading {entity}s...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="entity-list">
        <div className="entity-list-error">
          Error: {error}
        </div>
      </div>
    );
  }

  // Empty state (no items at all)
  if (safeItems.length === 0) {
    return (
      <div className="entity-list">
        <div className="entity-list-empty">
          <span className="entity-list-empty-text">No {entity}s found</span>
          <span className="entity-list-empty-hint">Results will appear here</span>
        </div>
      </div>
    );
  }

  // List view with filter bar
  return (
    <div className="entity-list">
      {showFilterBar && (
        <FilterBar
          properties={schema!.properties}
          filters={filters}
          onFilter={updateFilters}
          totalCount={safeItems.length}
          filteredCount={filteredItems.length}
        />
      )}
      {sortedItems.length === 0 ? (
        <div className="entity-list-empty">
          <span className="entity-list-empty-text">No matching {entity}s</span>
          <span className="entity-list-empty-hint">Try adjusting your filters</span>
        </div>
      ) : (
        <div className="entity-list-content">
          {sortedItems.map((item, index) => (
            <EntityListItem
              key={(item.id as string) || index}
              item={item}
              hints={effectiveHints}
              showCheckbox={showCheckbox}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default EntityList;
