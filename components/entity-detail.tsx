/**
 * Entity Detail Component
 * 
 * Detail view for single items (get operations).
 * Fetches entity schema for display hints and renders rich detail views:
 * 
 * - Image header from display.image (proxy + initials fallback)
 * - Relationship references rendered as linked cards
 * - Content fields (description, content) as text blocks
 * - Metadata fields with smart formatting (duration, counts, dates)
 * - Property sections grouped by type
 * 
 * This component replaces per-entity custom detail views (video-header,
 * post-header, group-header) with a single generic renderer that reads
 * the entity schema and renders accordingly.
 * 
 * Styles defined in base.css (.entity-detail-*)
 * 
 * @example
 * ```yaml
 * - component: entity-detail
 *   props:
 *     entity: "{{entity}}"
 *     item: "{{entities}}"
 *     pending: "{{loading}}"
 * ```
 */

import React, { useState, useEffect } from 'react';
import {
  getEntitySchema,
  getNestedValue,
  getProxiedSrc,
  extractImageUrl,
  getInitials,
  getColorFromString,
  inferImageVariant,
  isTypedReference,
  formatDuration,
  formatCount,
  formatRelativeTime,
  formatValue as baseFormatValue,
  getFieldLabel,
  getEmbedUrl,
} from '/ui/lib/utils.js';

interface EntityDetailProps {
  /** Entity type (e.g., 'task', 'post') */
  entity?: string;
  /** The item to display */
  item?: Record<string, unknown>;
  /** Whether data is still loading */
  pending?: boolean;
  /** Error message if request failed */
  error?: string;
}

interface DisplayHints {
  primary?: string;
  secondary?: string;
  description?: string;
  image?: string;
  status?: string;
  badge?: string;
  /** Metadata fields to show inline */
  meta?: string[];
  /** Field containing embeddable URL (e.g., "url" for video player) */
  embed?: string;
}

// Utilities imported from /lib/utils.js — detail view wraps formatValue to show dashes for null
function formatValue(value: unknown, key?: string): string {
  return baseFormatValue(value, key) || '\u2014';
}

const EXCLUDED_FIELDS = new Set([
  'id', 'skill', 'account', '_labels', '_project_id', '_entity_id',
  'remote_id', 'data', 'fetched_at',
]);

const CONTENT_FIELDS = new Set([
  'description', 'content', 'transcript', 'snippet', 'body', 'text', 'summary', 'notes',
]);

// ─── Sub-components ─────────────────────────────────────────────────────────────

/**
 * Image with proxy, error handling, and initials fallback.
 */
function DetailImage({
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
        className={`entity-detail-image entity-detail-image--${variant}`}
        src={proxied}
        alt={alt}
        onError={() => setError(true)}
        loading="lazy"
      />
    );
  }

  // Initials fallback
  return (
    <div
      className={`entity-detail-image-initials entity-detail-image-initials--${variant}`}
      style={{ backgroundColor: getColorFromString(alt) }}
      role="img"
      aria-label={alt}
    >
      {getInitials(alt)}
    </div>
  );
}

/**
 * Priority badge (Urgent/High/Medium/Low)
 */
function PriorityBadge({ priority }: { priority: number }) {
  const labels: Record<number, string> = { 1: 'Urgent', 2: 'High', 3: 'Medium', 4: 'Low' };
  return (
    <span data-component="badge" data-priority={priority} data-size="md">
      {labels[priority] || `P${priority}`}
    </span>
  );
}

/**
 * Status badge (Completed/In Progress)
 */
function StatusBadge({ completed }: { completed: boolean }) {
  return (
    <span
      data-component="badge"
      data-status={completed ? 'complete' : 'in-progress'}
      data-size="md"
    >
      {completed ? 'Completed' : 'In Progress'}
    </span>
  );
}

/**
 * Typed reference card — renders an entity reference as a linked element.
 * Natural structure: { account: { display_name: "3Blue1Brown", url: "..." }, _rel?: {...} }
 */
function TypedReference({
  label,
  value,
}: {
  label: string;
  value: Record<string, unknown>;
}) {
  // Extract entity type and data from natural structure
  const entityKeys = Object.keys(value).filter(k => !k.startsWith('_'));
  const entityType = entityKeys[0] || 'unknown';
  const entityData = value[entityType] as Record<string, unknown> | undefined;
  
  const type = entityType;
  const name = entityData 
    ? String(entityData.display_name || entityData.name || entityData.title || entityData.id || type)
    : type;
  const url = entityData?.url as string | undefined;

  return (
    <div className="entity-detail-field">
      <span className="entity-detail-field-label">{label}</span>
      <span className="entity-detail-field-value">
        <span className="entity-detail-reference">
          <span className="entity-detail-reference-type">{type}</span>
          {url ? (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="entity-detail-reference-name"
            >
              {name}
            </a>
          ) : (
            <span className="entity-detail-reference-name">{name}</span>
          )}
        </span>
      </span>
    </div>
  );
}

/**
 * Single field display (key-value pair with smart formatting)
 */
function Field({
  label,
  value,
  fieldKey,
}: {
  label: string;
  value: unknown;
  fieldKey: string;
}) {
  // Priority gets a badge
  if (fieldKey === 'priority' && typeof value === 'number') {
    return (
      <div className="entity-detail-field">
        <span className="entity-detail-field-label">{label}</span>
        <span className="entity-detail-field-value">
          <PriorityBadge priority={value} />
        </span>
      </div>
    );
  }

  // Completed gets a status badge
  if (fieldKey === 'completed' && typeof value === 'boolean') {
    return (
      <div className="entity-detail-field">
        <span className="entity-detail-field-label">Status</span>
        <span className="entity-detail-field-value">
          <StatusBadge completed={value} />
        </span>
      </div>
    );
  }

  return (
    <div className="entity-detail-field">
      <span className="entity-detail-field-label">{label}</span>
      <span className="entity-detail-field-value">{formatValue(value, fieldKey)}</span>
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────────────────────

export function EntityDetail({
  entity = 'item',
  item,
  pending = false,
  error,
}: EntityDetailProps) {
  const [schema, setSchema] = useState<{ display?: DisplayHints } | null>(null);

  useEffect(() => {
    if (!entity || entity === 'item') return;
    getEntitySchema(entity).then(setSchema);
  }, [entity]);

  const hints: DisplayHints = schema?.display || {};

  // Loading state
  if (pending) {
    return (
      <div className="entity-detail">
        <div className="app-view-loading">
          <div className="progress-bar" />
          <span className="app-view-loading-text">Loading {entity}...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="entity-detail">
        <div className="entity-detail-error">
          Error: {error}
        </div>
      </div>
    );
  }

  // Empty state
  if (!item) {
    return (
      <div className="entity-detail">
        <div className="entity-detail-empty">
          <span className="entity-detail-empty-text">No {entity} found</span>
        </div>
      </div>
    );
  }

  // ── Resolve display values ──────────────────────────────────────────────────

  const primaryField = hints.primary || 'title';
  const primaryValue = getNestedValue(item, primaryField) || item.title || item.name || item.content;
  const primaryText = String(primaryValue || 'Untitled');

  const secondaryValue = hints.secondary ? getNestedValue(item, hints.secondary) : undefined;
  const secondaryText = secondaryValue ? formatValue(secondaryValue, hints.secondary) : undefined;

  // Image
  const imageRaw = hints.image ? getNestedValue(item, hints.image) : undefined;
  const imageUrl = extractImageUrl(imageRaw);
  const hasImage = Boolean(hints.image);
  const imageVariant = inferImageVariant(hints.image);

  // Embed (video player, etc.)
  const embedField = hints.embed;
  const embedRawUrl = embedField ? String(getNestedValue(item, embedField) || '') : '';
  const embedUrl = embedRawUrl ? getEmbedUrl(embedRawUrl) : null;

  // Description (from schema hint or common field names)
  const descriptionField = hints.description;
  const descriptionValue = descriptionField
    ? getNestedValue(item, descriptionField)
    : (item.description || undefined);
  const descriptionText = descriptionValue ? String(descriptionValue) : undefined;

  // Content (separate from description)
  const contentText = item.content && item.content !== descriptionValue
    ? String(item.content)
    : undefined;

  // ── Classify fields into sections ───────────────────────────────────────────

  // Fields already shown in header/content sections
  const shownFields = new Set([
    primaryField, 'title', 'name', 'url',
    hints.secondary?.split('.')[0], // e.g., 'posted_by' from 'posted_by.display_name'
    hints.image,
    hints.description,
    hints.status,
    hints.badge,
    hints.embed,
    // Meta fields are shown inline in list view; in detail they stay in metadata section
  ]);

  // Separate remaining fields into relationships, content, and metadata
  const relationships: [string, Record<string, unknown>][] = [];
  const contentBlocks: [string, string][] = [];
  const metadataFields: [string, unknown][] = [];

  for (const [key, value] of Object.entries(item)) {
    if (EXCLUDED_FIELDS.has(key)) continue;
    if (shownFields.has(key)) continue;
    if (key === 'description' || key === 'content') continue; // handled above

    if (isTypedReference(value)) {
      relationships.push([key, value]);
    } else if (CONTENT_FIELDS.has(key) && typeof value === 'string' && value.length > 100) {
      contentBlocks.push([key, value]);
    } else if (Array.isArray(value)) {
      // Skip arrays (e.g., chapters, transcript_segments) — too complex for generic rendering
      continue;
    } else {
      metadataFields.push([key, value]);
    }
  }

  // ── Build header badges ─────────────────────────────────────────────────────

  // Resolve status via schema hint path (e.g., 'data.completed' for tasks)
  const statusValue = hints.status ? getNestedValue(item, hints.status) : undefined;
  const completed = typeof statusValue === 'boolean' ? statusValue : undefined;
  const priority = (item.priority ?? (item.data as Record<string, unknown>)?.priority) as number | undefined;

  const badges: React.ReactNode[] = [];
  if (completed !== undefined) {
    badges.push(<StatusBadge key="status" completed={completed} />);
  }
  if (priority !== undefined && typeof priority === 'number') {
    badges.push(<PriorityBadge key="priority" priority={priority} />);
  }
  if (item.due_date) {
    badges.push(
      <span key="due" data-component="badge" data-variant="due" data-size="md">
        Due: {formatValue(item.due_date, 'due_date')}
      </span>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="entity-detail">
      {/* Embed player (YouTube, Vimeo, etc.) — replaces static image when available */}
      {embedUrl ? (
        <div className="entity-detail-embed">
          <iframe
            className="entity-detail-embed-iframe"
            src={embedUrl}
            title={primaryText}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
      ) : hasImage ? (
        <div className="entity-detail-image-header">
          <DetailImage src={imageUrl} alt={primaryText} variant={imageVariant} />
        </div>
      ) : null}

      {/* Header section */}
      <div className="entity-detail-header">
        <h1 className="entity-detail-title">{primaryText}</h1>

        {secondaryText && (
          <div className="entity-detail-subtitle">{secondaryText}</div>
        )}

        {badges.length > 0 && (
          <div className="entity-detail-badges">{badges}</div>
        )}
      </div>

      {/* Content section */}
      <div className="entity-detail-content">
        {/* Description */}
        {descriptionText && descriptionText !== primaryText && (
          <div className="entity-detail-section">
            <div className="entity-detail-section-title">Description</div>
            <div className="entity-detail-text-block">{descriptionText}</div>
          </div>
        )}

        {/* Content (if different from description) */}
        {contentText && contentText !== primaryText && (
          <div className="entity-detail-section">
            <div className="entity-detail-section-title">Content</div>
            <div className="entity-detail-text-block">{contentText}</div>
          </div>
        )}

        {/* Additional content blocks (transcript, body, etc.) */}
        {contentBlocks.map(([key, text]) => (
          <div key={key} className="entity-detail-section">
            <div className="entity-detail-section-title">{getFieldLabel(key)}</div>
            <div className="entity-detail-text-block">{text}</div>
          </div>
        ))}

        {/* Relationships (typed references) */}
        {relationships.length > 0 && (
          <div className="entity-detail-section">
            <div className="entity-detail-section-title">Relationships</div>
            {relationships.map(([key, value]) => (
              <TypedReference
                key={key}
                label={getFieldLabel(key)}
                value={value}
              />
            ))}
          </div>
        )}

        {/* Metadata fields */}
        {metadataFields.length > 0 && (
          <div className="entity-detail-section">
            <div className="entity-detail-section-title">Details</div>
            {metadataFields.map(([key, value]) => (
              <Field
                key={key}
                label={getFieldLabel(key)}
                value={value}
                fieldKey={key}
              />
            ))}
          </div>
        )}
      </div>

      {/* URL link */}
      {typeof item.url === 'string' && (
        <div className="entity-detail-footer">
          <a
            href={item.url as string}
            target="_blank"
            rel="noopener noreferrer"
            className="entity-detail-item-link"
          >
            Open in source app
          </a>
        </div>
      )}
    </div>
  );
}

export default EntityDetail;
