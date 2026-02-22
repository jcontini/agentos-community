/**
 * Memex Detail View
 *
 * Universal entity renderer. Shows any entity's properties, content body,
 * and relationships — all driven by the entity schema. No entity-specific code.
 *
 * Layout:
 *   1. Title + type badge
 *   2. Property panel (Obsidian-style key-value metadata)
 *   3. Content area (markdown body)
 *   4. Relationship panel (graph connections)
 *
 * Properties are rendered with type-aware formatting: booleans as checkmarks,
 * enums as badges, URLs as links, dates as relative time, arrays as chips.
 * Provenance fields (skill, account, timestamps) shown last, muted.
 */

import React, { useState, useEffect } from 'react';
import {
  getEntitySchema,
  getNestedValue,
  isTypedReference,
  isUrl,
  getProxiedSrc,
  getInitials,
  getColorFromString,
  formatRelativeTime,
  formatDuration,
  formatCount,
  formatValue,
  getFieldLabel,
} from '/lib/utils.js';

// ─── Interfaces ──────────────────────────────────────────────────────────────────

interface MemexDetailProps {
  entity_type?: string;
  entity?: string;
  entity_id?: string;
  data?: Record<string, unknown>;
  item?: Record<string, unknown>;
  pending?: boolean;
  error?: string;
}

interface DisplayHints {
  primary?: string;
  secondary?: string;
  description?: string;
  image?: string;
  status?: string;
  icon?: string;
  meta?: string[];
  embed?: string;
}

interface PropertyDef {
  type?: string;
  description?: string;
  enum?: string[];
  format?: string;
  required?: boolean;
  references?: string;
}

// ─── Field Classification ────────────────────────────────────────────────────────

const INTERNAL_FIELDS = new Set([
  '_entity_id', '_labels', '_project_id', 'service_id', 'remote_id',
  'fetched_at', 'id', 'data',
]);

const CONTENT_FIELDS = new Set([
  'description', 'content', 'body', 'text', 'notes', 'transcript',
  'summary', 'snippet',
]);

const PROVENANCE_FIELDS = new Set([
  'skill', 'account', 'created_at', 'updated_at',
]);

// ─── Markdown Renderer ───────────────────────────────────────────────────────────

function renderMarkdown(content: string): string {
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, _lang, code) =>
    `<pre class="memex-code-block"><code>${code.trim()}</code></pre>`
  );
  html = html.replace(/`([^`]+)`/g, '<code class="memex-code-inline">$1</code>');
  html = html.replace(/^#### (.+)$/gm, '<h4 class="memex-md-h4">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="memex-md-h3">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="memex-md-h2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="memex-md-h1">$1</h1>');
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener" class="memex-link">$1</a>'
  );
  html = html.replace(/(?<!href="|">)(https?:\/\/[^\s<>"]+)/g,
    '<a href="$1" target="_blank" rel="noopener" class="memex-link">$1</a>'
  );
  html = html.replace(/^(?:---|\*\*\*|___)\s*$/gm, '<hr class="memex-hr" />');
  html = html.replace(/^> (.+)$/gm, '<blockquote class="memex-blockquote">$1</blockquote>');
  html = html.replace(/^[\*\-] (.+)$/gm, '<li class="memex-li">$1</li>');
  html = html.replace(/(<li class="memex-li">.*<\/li>\n?)+/g, '<ul class="memex-ul">$&</ul>');
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="memex-li-ordered">$1</li>');
  html = html.replace(/(<li class="memex-li-ordered">.*<\/li>\n?)+/g, '<ol class="memex-ol">$&</ol>');
  html = html.replace(/^(?!<[huplo]|<bl|<hr|<pre|<li)(.+)$/gm, '<p class="memex-p">$1</p>');
  html = html.replace(/\n\n+/g, '\n');
  return html;
}

// ─── Styles ──────────────────────────────────────────────────────────────────────

const S = {
  container: {
    maxWidth: 780, margin: '0 auto', padding: '24px 20px 48px',
    color: 'var(--content-fg)',
  } as React.CSSProperties,

  centered: {
    display: 'flex', flexDirection: 'column' as const,
    alignItems: 'center', justifyContent: 'center',
    padding: '80px 20px', gap: 12, opacity: 0.5,
  } as React.CSSProperties,

  imageHeader: {
    width: '100%', maxHeight: 280, objectFit: 'cover' as const,
    borderRadius: 8, marginBottom: 20,
  } as React.CSSProperties,

  avatarHeader: {
    width: 80, height: 80, borderRadius: '50%',
    objectFit: 'cover' as const, marginBottom: 16,
  } as React.CSSProperties,

  header: { marginBottom: 20 } as React.CSSProperties,

  title: {
    fontSize: 24, fontWeight: 600, lineHeight: 1.3,
    margin: '0 0 6px', color: 'var(--content-fg)',
  } as React.CSSProperties,

  typeBadge: {
    display: 'inline-block', fontSize: 11, fontWeight: 500,
    padding: '2px 8px', borderRadius: 4,
    background: 'var(--content-bg-secondary, rgba(128,128,128,0.1))',
    color: 'var(--content-fg-muted)', textTransform: 'capitalize' as const,
  } as React.CSSProperties,

  section: { marginBottom: 24 } as React.CSSProperties,

  sectionHeader: {
    display: 'flex', alignItems: 'center', gap: 8,
    marginBottom: 12, paddingBottom: 6,
    borderBottom: '1px solid var(--content-border-subtle, rgba(128,128,128,0.15))',
  } as React.CSSProperties,

  sectionTitle: {
    fontSize: 11, fontWeight: 600, textTransform: 'uppercase' as const,
    letterSpacing: '0.05em', color: 'var(--content-fg-muted)',
  } as React.CSSProperties,

  propRow: {
    display: 'flex', alignItems: 'baseline', padding: '5px 0',
    gap: 12, fontSize: 13, lineHeight: 1.5,
  } as React.CSSProperties,

  propLabel: {
    flexShrink: 0, width: 130, color: 'var(--content-fg-muted)',
    fontSize: 12, fontWeight: 500,
  } as React.CSSProperties,

  propValue: {
    flex: 1, color: 'var(--content-fg)', wordBreak: 'break-word' as const,
  } as React.CSSProperties,

  divider: {
    height: 1, background: 'var(--content-border-subtle, rgba(128,128,128,0.1))',
    margin: '8px 0',
  } as React.CSSProperties,

  chip: {
    display: 'inline-block', fontSize: 11, padding: '1px 7px', borderRadius: 3,
    background: 'var(--content-bg-secondary, rgba(128,128,128,0.1))',
    color: 'var(--content-fg-muted)', marginRight: 4, marginBottom: 2,
  } as React.CSSProperties,

  link: { color: 'var(--link-color-subtle, #6b9eff)', textDecoration: 'none' } as React.CSSProperties,

  relRow: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
    borderRadius: 6, fontSize: 13,
  } as React.CSSProperties,

  relType: {
    flexShrink: 0, width: 100, fontSize: 11, fontWeight: 500,
    color: 'var(--content-fg-muted)',
  } as React.CSSProperties,

  relEntity: {
    display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0,
  } as React.CSSProperties,

  relAvatar: {
    width: 22, height: 22, borderRadius: '50%',
    objectFit: 'cover' as const, flexShrink: 0,
  } as React.CSSProperties,

  relInitials: {
    width: 22, height: 22, borderRadius: '50%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 9, fontWeight: 600, color: '#fff', flexShrink: 0,
  } as React.CSSProperties,
};

// ─── Sub-Components ──────────────────────────────────────────────────────────────

function PropertyRow({ label, value, fieldKey, propertyDef }: {
  label: string; value: unknown; fieldKey: string; propertyDef?: PropertyDef;
}) {
  if (typeof value === 'boolean') {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <span style={{ color: value ? 'var(--accent-color, #4caf50)' : 'var(--content-fg-muted)', fontWeight: 600 }}>
            {value ? '\u2713 Yes' : '\u2717 No'}
          </span>
        </span>
      </div>
    );
  }

  if (propertyDef?.enum && typeof value === 'string') {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}><span style={S.chip}>{value}</span></span>
      </div>
    );
  }

  if (isUrl(value)) {
    const display = String(value).replace(/^https?:\/\/(www\.)?/, '');
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <a href={String(value)} target="_blank" rel="noopener noreferrer" style={S.link}>
            {display.length > 60 ? display.slice(0, 57) + '...' : display}
          </a>
        </span>
      </div>
    );
  }

  if (Array.isArray(value) && value.every(v => typeof v === 'string')) {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={{ ...S.propValue, display: 'flex', flexWrap: 'wrap', gap: 2 }}>
          {(value as string[]).map((v, i) => <span key={i} style={S.chip}>{v}</span>)}
        </span>
      </div>
    );
  }

  return (
    <div className="memex-property" style={S.propRow}>
      <span style={S.propLabel}>{label}</span>
      <span style={S.propValue}>{formatValue(value, fieldKey) || '\u2014'}</span>
    </div>
  );
}

function PropertyPanel({ properties, provenanceFields, schema }: {
  properties: [string, unknown, PropertyDef | undefined][];
  provenanceFields: [string, unknown][];
  schema: { properties?: Record<string, PropertyDef> } | null;
}) {
  if (properties.length === 0 && provenanceFields.length === 0) return null;
  return (
    <div className="memex-section memex-section--properties" style={S.section}>
      <div style={S.sectionHeader}>
        <span style={S.sectionTitle}>Properties</span>
      </div>
      <div className="memex-properties">
        {properties.map(([key, value, propDef]) => (
          <PropertyRow key={key} label={getFieldLabel(key)} value={value}
            fieldKey={key} propertyDef={propDef} />
        ))}
        {provenanceFields.length > 0 && (
          <>
            <div style={S.divider} />
            {provenanceFields.map(([key, value]) => (
              <PropertyRow key={key} label={getFieldLabel(key)} value={value} fieldKey={key} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function ContentArea({ content, label }: { content: string; label?: string }) {
  return (
    <div className="memex-section memex-section--content" style={S.section}>
      {label && (
        <div style={S.sectionHeader}><span style={S.sectionTitle}>{label}</span></div>
      )}
      <div
        className="memex-content"
        style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--content-fg)' }}
        dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
      />
    </div>
  );
}

function RelationshipPanel({ relationships }: {
  relationships: [string, Record<string, unknown>][];
}) {
  if (relationships.length === 0) return null;
  return (
    <div className="memex-section memex-section--relationships" style={S.section}>
      <div style={S.sectionHeader}>
        <span style={S.sectionTitle}>Relationships</span>
        <span style={{ fontSize: 11, color: 'var(--content-fg-muted)' }}>
          {relationships.length}
        </span>
      </div>
      <div className="memex-relationships">
        {relationships.map(([relType, relData]) => {
          const entityKeys = Object.keys(relData).filter(k => !k.startsWith('_'));
          return entityKeys.map(entityType => {
            const entity = relData[entityType] as Record<string, unknown>;
            if (!entity || typeof entity !== 'object') return null;
            const name = String(
              entity.display_name || entity.name || entity.title || entity.id || entityType
            );
            const image = (entity.icon || entity.avatar || entity.thumbnail) as string | undefined;
            return (
              <div key={`${relType}-${entityType}`} className="memex-relationship" style={S.relRow}>
                <span style={S.relType}>{getFieldLabel(relType)}</span>
                <span style={{ color: 'var(--content-fg-muted)', fontSize: 12 }}>&rarr;</span>
                <div style={S.relEntity}>
                  {image ? (
                    <img src={getProxiedSrc(image)} alt="" style={S.relAvatar}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                  ) : (
                    <span style={{ ...S.relInitials, backgroundColor: getColorFromString(name) }}>
                      {getInitials(name)}
                    </span>
                  )}
                  <span style={{ color: 'var(--content-fg)', fontWeight: 500,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                    {name}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--content-fg-muted)', flexShrink: 0 }}>
                    {entityType}
                  </span>
                </div>
              </div>
            );
          });
        })}
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────────

export default function MemexDetail({
  entity_type, entity, entity_id, data, item, pending, error,
}: MemexDetailProps) {
  const type = entity_type || entity || 'item';
  const entityData = data || item;

  const [schema, setSchema] = useState<{
    display?: DisplayHints; properties?: Record<string, PropertyDef>;
  } | null>(null);

  useEffect(() => {
    if (!type || type === 'item') return;
    getEntitySchema(type).then(setSchema);
  }, [type]);

  const hints = schema?.display || {};

  if (pending) {
    return <div className="memex-detail" style={S.container}>
      <div style={S.centered}><div className="progress-bar" /><span>Loading...</span></div>
    </div>;
  }
  if (error) {
    return <div className="memex-detail" style={S.container}>
      <div style={S.centered}><span>Error: {error}</span></div>
    </div>;
  }
  if (!entityData) {
    return <div className="memex-detail" style={S.container}>
      <div style={S.centered}><span>No data</span></div>
    </div>;
  }

  const primaryField = hints.primary || 'title';
  const primaryValue = getNestedValue(entityData, primaryField) || entityData.title || entityData.name;
  const title = primaryValue ? String(primaryValue) : 'Untitled';

  const imageField = hints.image;
  const imageRaw = imageField ? getNestedValue(entityData, imageField) : undefined;
  const imageSrc = typeof imageRaw === 'string' ? getProxiedSrc(imageRaw) : undefined;
  const isAvatar = Boolean(imageField && /icon|favicon|avatar|logo|profile/.test(imageField));

  // Classify fields
  const properties: [string, unknown, PropertyDef | undefined][] = [];
  const contentBlocks: [string, string][] = [];
  const relationships: [string, Record<string, unknown>][] = [];
  const provenanceFields: [string, unknown][] = [];

  const titleFields = new Set([primaryField, 'title', 'name']);
  const hintFields = new Set(
    [hints.secondary?.split('.')[0], hints.image, hints.embed].filter(Boolean) as string[]
  );

  for (const [key, value] of Object.entries(entityData)) {
    if (INTERNAL_FIELDS.has(key)) continue;
    if (titleFields.has(key) && String(value) === title) continue;
    if (hintFields.has(key)) continue;
    if (value === null || value === undefined) continue;

    if (PROVENANCE_FIELDS.has(key)) { provenanceFields.push([key, value]); continue; }
    if (isTypedReference(value)) { relationships.push([key, value as Record<string, unknown>]); continue; }
    if (CONTENT_FIELDS.has(key) && typeof value === 'string' && value.length > 200) {
      contentBlocks.push([key, value]); continue;
    }
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') continue;

    properties.push([key, value, schema?.properties?.[key]]);
  }

  return (
    <div className="memex-detail" style={S.container}>
      {imageSrc && (
        <img className="memex-detail-image" src={imageSrc} alt={title}
          style={isAvatar ? S.avatarHeader : S.imageHeader}
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
      )}

      <div className="memex-detail-header" style={S.header}>
        <h1 className="memex-detail-title" style={S.title}>{title}</h1>
        {type !== 'item' && <span style={S.typeBadge}>{type}</span>}
      </div>

      <PropertyPanel properties={properties} provenanceFields={provenanceFields} schema={schema} />

      {contentBlocks.map(([key, text]) => (
        <ContentArea key={key} content={text}
          label={contentBlocks.length > 1 ? getFieldLabel(key) : undefined} />
      ))}

      <RelationshipPanel relationships={relationships} />
    </div>
  );
}
