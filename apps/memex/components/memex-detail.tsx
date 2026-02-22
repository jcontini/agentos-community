/**
 * Memex Detail View
 *
 * Universal entity renderer with inline property editing.
 *
 * Layout:
 *   1. Title (editable) + type badge
 *   2. Property panel — always-editable, type-aware controls
 *   3. Source line (subtle: "via Todoist · 2h ago")
 *   4. Content area (markdown body, read-only for now)
 *   5. Relationship panel (graph connections)
 *
 * Properties are inline-editable with controls matched to schema types:
 * booleans as toggles, enums as dropdowns, dates as date pickers,
 * text/numbers as seamless inputs. Auto-saves on change via PATCH.
 *
 * No skill ownership — the user owns the graph. All properties are
 * editable regardless of where the entity came from.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  apiFetch,
  getEntitySchema,
  getNestedValue,
  isTypedReference,
  isUrl,
  getProxiedSrc,
  getInitials,
  getColorFromString,
  formatRelativeTime,
  formatValue,
  getFieldLabel,
} from '/ui/lib/utils.js';

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

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

// ─── Field Classification ────────────────────────────────────────────────────────

const INTERNAL_FIELDS = new Set([
  '_entity_id', '_labels', '_project_id', 'service_id', 'remote_id',
  'fetched_at', 'id', 'data',
]);

const CONTENT_FIELDS = new Set([
  'description', 'content', 'body', 'text', 'notes', 'transcript',
  'summary', 'snippet',
]);

const LIFECYCLE_FIELDS = new Set([
  'skill', 'account', 'created_at', 'updated_at',
]);

const KNOWN_PLURALS: Record<string, string> = {
  person: 'people', child: 'children', analysis: 'analyses',
};

function getPlural(type: string, schema: Record<string, unknown> | null): string {
  if (schema && typeof (schema as any).plural === 'string') return (schema as any).plural;
  if (KNOWN_PLURALS[type]) return KNOWN_PLURALS[type];
  return type + 's';
}

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
    background: 'transparent', border: '1px solid transparent',
    borderRadius: 4, padding: '2px 4px', marginLeft: -5,
    width: '100%', boxSizing: 'border-box' as const,
    fontFamily: 'inherit', outline: 'none',
  } as React.CSSProperties,

  titleFocused: {
    borderColor: 'var(--accent-color, #6b9eff)',
    background: 'var(--content-bg-secondary, rgba(128,128,128,0.06))',
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
    display: 'flex', alignItems: 'center', padding: '4px 0',
    gap: 12, fontSize: 13, lineHeight: 1.5, minHeight: 30,
  } as React.CSSProperties,

  propLabel: {
    flexShrink: 0, width: 130, color: 'var(--content-fg-muted)',
    fontSize: 12, fontWeight: 500,
  } as React.CSSProperties,

  propValue: {
    flex: 1, color: 'var(--content-fg)', wordBreak: 'break-word' as const,
    display: 'flex', alignItems: 'center', gap: 6,
  } as React.CSSProperties,

  input: {
    background: 'transparent',
    border: '1px solid transparent',
    borderRadius: 4,
    padding: '3px 6px',
    fontSize: 13,
    fontFamily: 'inherit',
    color: 'var(--content-fg)',
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box' as const,
    transition: 'border-color 0.15s, background 0.15s',
  } as React.CSSProperties,

  inputHover: {
    borderColor: 'var(--content-border-subtle, rgba(128,128,128,0.25))',
  } as React.CSSProperties,

  inputFocus: {
    borderColor: 'var(--accent-color, #6b9eff)',
    background: 'var(--content-bg-secondary, rgba(128,128,128,0.06))',
  } as React.CSSProperties,

  select: {
    background: 'transparent',
    border: '1px solid transparent',
    borderRadius: 4,
    padding: '3px 6px',
    fontSize: 13,
    fontFamily: 'inherit',
    color: 'var(--content-fg)',
    outline: 'none',
    cursor: 'pointer',
    transition: 'border-color 0.15s',
  } as React.CSSProperties,

  checkbox: {
    width: 16, height: 16, cursor: 'pointer',
    accentColor: 'var(--accent-color, #6b9eff)',
  } as React.CSSProperties,

  chip: {
    display: 'inline-block', fontSize: 11, padding: '1px 7px', borderRadius: 3,
    background: 'var(--content-bg-secondary, rgba(128,128,128,0.1))',
    color: 'var(--content-fg-muted)', marginRight: 4, marginBottom: 2,
  } as React.CSSProperties,

  saveIndicator: {
    fontSize: 11, flexShrink: 0, width: 16, textAlign: 'center' as const,
  } as React.CSSProperties,

  sourceLine: {
    fontSize: 11, color: 'var(--content-fg-muted)',
    padding: '4px 0 0', marginBottom: 20,
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

// ─── Editable Property Row ───────────────────────────────────────────────────────

function EditablePropertyRow({ label, value, fieldKey, propertyDef, saveStatus, onSave }: {
  label: string;
  value: unknown;
  fieldKey: string;
  propertyDef?: PropertyDef;
  saveStatus: SaveStatus;
  onSave: (key: string, value: unknown) => void;
}) {
  const [hover, setHover] = useState(false);
  const [focused, setFocused] = useState(false);
  const inputStyle = { ...S.input, ...(focused ? S.inputFocus : hover ? S.inputHover : {}) };

  const indicator = saveStatus === 'saving'
    ? <span style={{ ...S.saveIndicator, color: 'var(--content-fg-muted)' }}>...</span>
    : saveStatus === 'saved'
    ? <span style={{ ...S.saveIndicator, color: 'var(--accent-color, #4caf50)' }}>{'\u2713'}</span>
    : saveStatus === 'error'
    ? <span style={{ ...S.saveIndicator, color: '#e57373' }}>!</span>
    : null;

  // Boolean → checkbox toggle
  if (typeof value === 'boolean' || propertyDef?.type === 'boolean') {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onSave(fieldKey, e.target.checked)}
            style={S.checkbox}
          />
          <span style={{ color: 'var(--content-fg-muted)', fontSize: 12 }}>
            {value ? 'Yes' : 'No'}
          </span>
          {indicator}
        </span>
      </div>
    );
  }

  // Enum → dropdown
  if (propertyDef?.enum && propertyDef.enum.length > 0) {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <select
            value={value != null ? String(value) : ''}
            onChange={(e) => onSave(fieldKey, e.target.value)}
            style={{ ...S.select, ...(hover ? S.inputHover : {}) }}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
          >
            <option value="">--</option>
            {propertyDef.enum.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
          {indicator}
        </span>
      </div>
    );
  }

  // Date → date input
  if (propertyDef?.type === 'date' || (propertyDef?.type === 'string' && /date/.test(fieldKey))) {
    const dateStr = value ? String(value).slice(0, 10) : '';
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <input
            type="date"
            value={dateStr}
            onChange={(e) => onSave(fieldKey, e.target.value || null)}
            style={inputStyle}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
          />
          {indicator}
        </span>
      </div>
    );
  }

  // Datetime → datetime-local input
  if (propertyDef?.type === 'datetime') {
    const dtStr = value ? String(value).slice(0, 16) : '';
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <input
            type="datetime-local"
            value={dtStr}
            onChange={(e) => onSave(fieldKey, e.target.value || null)}
            style={inputStyle}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
          />
          {indicator}
        </span>
      </div>
    );
  }

  // Number → number input
  if (propertyDef?.type === 'integer' || propertyDef?.type === 'number') {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <input
            type="number"
            defaultValue={value != null ? Number(value) : ''}
            onFocus={() => setFocused(true)}
            onBlur={(e) => {
              setFocused(false);
              const v = e.target.value === '' ? null : Number(e.target.value);
              if (v !== value) onSave(fieldKey, v);
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
            style={{ ...inputStyle, maxWidth: 120 }}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
          />
          {indicator}
        </span>
      </div>
    );
  }

  // URL → text input with link
  if (isUrl(value) || propertyDef?.format === 'url') {
    return (
      <div className="memex-property" style={S.propRow}>
        <span style={S.propLabel}>{label}</span>
        <span style={S.propValue}>
          <input
            type="url"
            defaultValue={value != null ? String(value) : ''}
            onFocus={() => setFocused(true)}
            onBlur={(e) => {
              setFocused(false);
              if (e.target.value !== String(value ?? '')) onSave(fieldKey, e.target.value || null);
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
            style={inputStyle}
            placeholder="https://..."
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
          />
          {value && (
            <a href={String(value)} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 11, color: 'var(--content-fg-muted)', flexShrink: 0 }}
              title="Open link"
            >{'\u2197'}</a>
          )}
          {indicator}
        </span>
      </div>
    );
  }

  // Default: string → text input
  return (
    <div className="memex-property" style={S.propRow}>
      <span style={S.propLabel}>{label}</span>
      <span style={S.propValue}>
        <input
          type="text"
          defaultValue={value != null ? String(value) : ''}
          onFocus={() => setFocused(true)}
          onBlur={(e) => {
            setFocused(false);
            if (e.target.value !== String(value ?? '')) onSave(fieldKey, e.target.value || null);
          }}
          onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
          style={inputStyle}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
        />
        {indicator}
      </span>
    </div>
  );
}

// ─── Property Panel ──────────────────────────────────────────────────────────────

function PropertyPanel({ properties, saveStatuses, onSave }: {
  properties: [string, unknown, PropertyDef | undefined][];
  saveStatuses: Record<string, SaveStatus>;
  onSave: (key: string, value: unknown) => void;
}) {
  if (properties.length === 0) return null;
  return (
    <div className="memex-section memex-section--properties" style={S.section}>
      <div style={S.sectionHeader}>
        <span style={S.sectionTitle}>Properties</span>
      </div>
      <div className="memex-properties">
        {properties.map(([key, value, propDef]) => (
          <EditablePropertyRow
            key={key}
            label={getFieldLabel(key)}
            value={value}
            fieldKey={key}
            propertyDef={propDef}
            saveStatus={saveStatuses[key] || 'idle'}
            onSave={onSave}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Source Line ──────────────────────────────────────────────────────────────────

function SourceLine({ entityData }: { entityData: Record<string, unknown> }) {
  const parts: string[] = [];
  if (entityData.skill) parts.push(`via ${entityData.skill}`);
  if (entityData.account) parts.push(String(entityData.account));
  if (entityData.updated_at) parts.push(formatRelativeTime(entityData.updated_at));
  else if (entityData.created_at) parts.push(formatRelativeTime(entityData.created_at));

  if (parts.length === 0) return null;
  return <div className="memex-source" style={S.sourceLine}>{parts.join(' \u00B7 ')}</div>;
}

// ─── Content Area ────────────────────────────────────────────────────────────────

function ContentArea({ content, label, fieldKey, saveStatus, onSave }: {
  content: string;
  label?: string;
  fieldKey: string;
  saveStatus: SaveStatus;
  onSave: (key: string, value: unknown) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { setDraft(content); }, [content]);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.selectionStart = textareaRef.current.value.length;
    }
  }, [editing]);

  const handleSave = () => {
    setEditing(false);
    if (draft !== content) onSave(fieldKey, draft);
  };

  const statusText = saveStatus === 'saving' ? 'saving...'
    : saveStatus === 'saved' ? 'saved'
    : saveStatus === 'error' ? 'error saving'
    : null;

  return (
    <div className="memex-section memex-section--content" style={S.section}>
      <div style={S.sectionHeader}>
        {label && <span style={S.sectionTitle}>{label}</span>}
        {!label && <span style={S.sectionTitle}>Content</span>}
        <div style={{ flex: 1 }} />
        {statusText && (
          <span style={{
            fontSize: 11,
            color: saveStatus === 'error' ? '#e57373' : saveStatus === 'saved' ? 'var(--accent-color, #4caf50)' : 'var(--content-fg-muted)',
          }}>{statusText}</span>
        )}
        <button
          onClick={() => { if (editing) handleSave(); else setEditing(true); }}
          style={{
            background: 'none', border: '1px solid var(--content-border-subtle, rgba(128,128,128,0.2))',
            borderRadius: 4, padding: '2px 10px', fontSize: 11, fontWeight: 500,
            color: 'var(--content-fg-muted)', cursor: 'pointer',
          }}
        >
          {editing ? 'Done' : 'Edit'}
        </button>
      </div>

      {editing ? (
        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') { setDraft(content); setEditing(false); }
            if (e.key === 's' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSave(); }
          }}
          style={{
            width: '100%', minHeight: 200, padding: '12px',
            fontSize: 13, lineHeight: 1.6, fontFamily: 'monospace',
            color: 'var(--content-fg)',
            background: 'var(--content-bg-secondary, rgba(128,128,128,0.04))',
            border: '1px solid var(--content-border-subtle, rgba(128,128,128,0.2))',
            borderRadius: 6, outline: 'none', resize: 'vertical',
            boxSizing: 'border-box',
          }}
          spellCheck={false}
        />
      ) : (
        <div
          className="memex-content"
          style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--content-fg)', cursor: 'text' }}
          onClick={() => setEditing(true)}
          dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
        />
      )}
    </div>
  );
}

// ─── Relationship Panel ──────────────────────────────────────────────────────────

interface RawRelationship {
  id: string;
  type: string;
  from_entity: string;
  to_entity: string;
  data?: Record<string, unknown>;
}

function RelationshipPanel({ entityId, plural, relationships }: {
  entityId: string;
  plural: string;
  relationships: [string, Record<string, unknown>][];
}) {
  const [rawRels, setRawRels] = useState<RawRelationship[]>([]);
  const [adding, setAdding] = useState(false);
  const [relType, setRelType] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<Record<string, unknown>>>([]);
  const [searching, setSearching] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [addStatus, setAddStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch raw relationships for mutation IDs
  useEffect(() => {
    if (!entityId || !plural) return;
    apiFetch(`/mem/${plural}/${entityId}/relationships`)
      .then(r => r.ok ? r.json() : { relationships: [] })
      .then(data => setRawRels(data.relationships || []))
      .catch(() => {});
  }, [entityId, plural]);

  // Debounced entity search for the add form
  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (!searchQuery.trim()) { setSearchResults([]); return; }
    searchTimeout.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await apiFetch('/mem/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: searchQuery.trim() }),
        });
        if (!res.ok) throw new Error();
        const data = await res.json();
        setSearchResults(Array.isArray(data) ? data : (data.data || []));
      } catch { setSearchResults([]); }
      finally { setSearching(false); }
    }, 300);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [searchQuery]);

  const handleDelete = useCallback(async (relId: string) => {
    setDeletingId(relId);
    try {
      await apiFetch(`/mem/${plural}/${entityId}/relationships/${relId}`, { method: 'DELETE' });
      setRawRels(prev => prev.filter(r => r.id !== relId));
    } catch (err) {
      console.error('Failed to delete relationship:', err);
    }
    setDeletingId(null);
  }, [entityId, plural]);

  const handleAdd = useCallback(async (targetId: string) => {
    if (!relType.trim()) return;
    setAddStatus('saving');
    try {
      const res = await apiFetch(`/mem/${plural}/${entityId}/relationships`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: relType.trim(), to: targetId }),
      });
      if (!res.ok) throw new Error(await res.text());
      setAddStatus('saved');
      setAdding(false);
      setRelType('');
      setSearchQuery('');
      setSearchResults([]);
      // Re-fetch relationships
      const updated = await apiFetch(`/mem/${plural}/${entityId}/relationships`);
      if (updated.ok) {
        const data = await updated.json();
        setRawRels(data.relationships || []);
      }
      setTimeout(() => setAddStatus('idle'), 1500);
    } catch (err) {
      console.error('Failed to create relationship:', err);
      setAddStatus('error');
      setTimeout(() => setAddStatus('idle'), 3000);
    }
  }, [entityId, plural, relType]);

  // Find raw relationship ID for a displayed relationship (match by type)
  const findRawRelId = (relType: string, targetEntityId?: string): string | undefined => {
    return rawRels.find(r =>
      r.type === relType && (
        !targetEntityId ||
        r.to_entity === targetEntityId ||
        r.from_entity === targetEntityId
      )
    )?.id;
  };

  const hasRelationships = relationships.length > 0 || rawRels.length > 0;

  return (
    <div className="memex-section memex-section--relationships" style={S.section}>
      <div style={S.sectionHeader}>
        <span style={S.sectionTitle}>Relationships</span>
        {hasRelationships && (
          <span style={{ fontSize: 11, color: 'var(--content-fg-muted)' }}>
            {relationships.length}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {addStatus === 'saved' && (
          <span style={{ fontSize: 11, color: 'var(--accent-color, #4caf50)' }}>linked</span>
        )}
        <button
          onClick={() => setAdding(!adding)}
          style={{
            background: 'none', border: '1px solid var(--content-border-subtle, rgba(128,128,128,0.2))',
            borderRadius: 4, padding: '2px 10px', fontSize: 11, fontWeight: 500,
            color: 'var(--content-fg-muted)', cursor: 'pointer',
          }}
        >
          {adding ? 'Cancel' : 'Link'}
        </button>
      </div>

      {/* Existing relationships */}
      {relationships.length > 0 && (
        <div className="memex-relationships">
          {relationships.map(([relTypeKey, relData]) => {
            const entityKeys = Object.keys(relData).filter(k => !k.startsWith('_'));
            return entityKeys.map(entityType => {
              const entity = relData[entityType] as Record<string, unknown>;
              if (!entity || typeof entity !== 'object') return null;
              const name = String(
                entity.display_name || entity.name || entity.title || entity.id || entityType
              );
              const image = (entity.icon || entity.avatar || entity.thumbnail) as string | undefined;
              const targetId = (entity._entity_id || entity.id) as string | undefined;
              const rawRelId = findRawRelId(relTypeKey, targetId);

              return (
                <div key={`${relTypeKey}-${entityType}`} className="memex-relationship"
                  style={{ ...S.relRow, justifyContent: 'space-between' }}>
                  <span style={S.relType}>{getFieldLabel(relTypeKey)}</span>
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
                  {rawRelId && (
                    <button
                      onClick={() => handleDelete(rawRelId)}
                      disabled={deletingId === rawRelId}
                      style={{
                        background: 'none', border: 'none', padding: '2px 6px',
                        fontSize: 12, color: 'var(--content-fg-muted)', cursor: 'pointer',
                        opacity: deletingId === rawRelId ? 0.3 : 0.5,
                        flexShrink: 0,
                      }}
                      title="Remove relationship"
                    >{'\u00D7'}</button>
                  )}
                </div>
              );
            });
          })}
        </div>
      )}

      {/* Empty state */}
      {!hasRelationships && !adding && (
        <div style={{ fontSize: 12, color: 'var(--content-fg-muted)', padding: '8px 0' }}>
          No relationships yet
        </div>
      )}

      {/* Add relationship form */}
      {adding && (
        <div className="memex-relationship-add" style={{
          marginTop: 12, padding: 12,
          background: 'var(--content-bg-secondary, rgba(128,128,128,0.04))',
          borderRadius: 6, border: '1px solid var(--content-border-subtle, rgba(128,128,128,0.15))',
        }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <input
              type="text"
              value={relType}
              onChange={(e) => setRelType(e.target.value)}
              placeholder="Relationship type (e.g. enables, references)"
              list="memex-rel-types"
              style={{
                ...S.input,
                borderColor: 'var(--content-border-subtle, rgba(128,128,128,0.2))',
                flex: '0 0 220px',
              }}
            />
            <datalist id="memex-rel-types">
              {['enables', 'references', 'tag', 'assign', 'upload', 'cite',
                'link_to', 'replies_to', 'add_to', 'includes'].map(t => (
                <option key={t} value={t} />
              ))}
            </datalist>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search for entity to link..."
              style={{
                ...S.input,
                borderColor: 'var(--content-border-subtle, rgba(128,128,128,0.2))',
                flex: 1,
              }}
            />
          </div>

          {/* Search results */}
          {searching && (
            <div style={{ fontSize: 12, color: 'var(--content-fg-muted)', padding: '4px 0' }}>
              Searching...
            </div>
          )}
          {searchResults.length > 0 && (
            <div style={{ maxHeight: 200, overflowY: 'auto' }}>
              {searchResults.slice(0, 8).map((result, i) => {
                const rName = String(result.name || result.title || result.id || 'Untitled');
                const rId = (result._entity_id || result.id) as string;
                const rType = (result._labels || '') as string;
                return (
                  <div
                    key={rId || i}
                    onClick={() => rId && handleAdd(rId)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 8px', borderRadius: 4, cursor: 'pointer',
                      fontSize: 12,
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'var(--content-bg-secondary, rgba(128,128,128,0.08))'; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                  >
                    <span style={{
                      ...S.relInitials,
                      backgroundColor: getColorFromString(rName),
                      width: 20, height: 20, fontSize: 8,
                    }}>
                      {getInitials(rName)}
                    </span>
                    <span style={{ fontWeight: 500, color: 'var(--content-fg)' }}>{rName}</span>
                    {rType && <span style={{ color: 'var(--content-fg-muted)', fontSize: 10 }}>{rType}</span>}
                  </div>
                );
              })}
            </div>
          )}

          {searchQuery && !searching && searchResults.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--content-fg-muted)', padding: '4px 0' }}>
              No entities found for "{searchQuery}"
            </div>
          )}

          {addStatus === 'saving' && (
            <div style={{ fontSize: 12, color: 'var(--content-fg-muted)', padding: '4px 0' }}>
              Linking...
            </div>
          )}
          {addStatus === 'error' && (
            <div style={{ fontSize: 12, color: '#e57373', padding: '4px 0' }}>
              Failed to create link
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────────

export default function MemexDetail({
  entity_type, entity, entity_id, data, item, pending, error,
}: MemexDetailProps) {
  const type = entity_type || entity || 'item';
  const [entityData, setEntityData] = useState<Record<string, unknown> | null>(data || item || null);
  const [schema, setSchema] = useState<any>(null);
  const [saveStatuses, setSaveStatuses] = useState<Record<string, SaveStatus>>({});
  const [titleFocused, setTitleFocused] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setEntityData(data || item || null); }, [data, item]);

  useEffect(() => {
    if (!type || type === 'item') return;
    getEntitySchema(type).then(setSchema);
  }, [type]);

  const hints: DisplayHints = schema?.display || {};
  const plural = getPlural(type, schema);

  // Save a property change via PATCH
  const handleSave = useCallback(async (fieldKey: string, newValue: unknown) => {
    if (!entityData) return;
    const id = entityData._entity_id || entityData.id;
    if (!id) return;

    setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'saving' }));

    try {
      const res = await apiFetch(`/mem/${plural}/${id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ [fieldKey]: newValue }),
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => 'Save failed');
        console.error(`Save failed for ${fieldKey}:`, errText);
        setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'error' }));
        setTimeout(() => setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'idle' })), 3000);
        return;
      }

      setEntityData(prev => prev ? { ...prev, [fieldKey]: newValue } : prev);
      setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'saved' }));
      setTimeout(() => setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'idle' })), 1500);
    } catch (err) {
      console.error(`Save error for ${fieldKey}:`, err);
      setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'error' }));
      setTimeout(() => setSaveStatuses(prev => ({ ...prev, [fieldKey]: 'idle' })), 3000);
    }
  }, [entityData, plural]);

  // Save title
  const handleTitleSave = useCallback((newTitle: string) => {
    if (!entityData) return;
    const primaryField = hints.primary || 'title';
    const currentTitle = getNestedValue(entityData, primaryField) || entityData.title || entityData.name;
    if (newTitle === String(currentTitle)) return;

    const nameField = entityData.name !== undefined ? 'name' : 'title';
    handleSave(nameField, newTitle);
  }, [entityData, hints, handleSave]);

  // ── States ──

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

  // ── Resolve fields ──

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

  const titleFields = new Set([primaryField, 'title', 'name']);
  const hintFields = new Set(
    [hints.secondary?.split('.')[0], hints.image, hints.embed].filter(Boolean) as string[]
  );

  for (const [key, value] of Object.entries(entityData)) {
    if (INTERNAL_FIELDS.has(key)) continue;
    if (LIFECYCLE_FIELDS.has(key)) continue;
    if (titleFields.has(key) && String(value) === title) continue;
    if (hintFields.has(key)) continue;
    if (value === null || value === undefined) continue;

    if (isTypedReference(value)) { relationships.push([key, value as Record<string, unknown>]); continue; }
    if (CONTENT_FIELDS.has(key) && typeof value === 'string' && value.length > 200) {
      contentBlocks.push([key, value]); continue;
    }
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') continue;

    properties.push([key, value, schema?.properties?.[key]]);
  }

  // ── Render ──

  return (
    <div className="memex-detail" style={S.container}>
      {imageSrc && (
        <img className="memex-detail-image" src={imageSrc} alt={title}
          style={isAvatar ? S.avatarHeader : S.imageHeader}
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
      )}

      {/* Editable title */}
      <div className="memex-detail-header" style={S.header}>
        <input
          ref={titleRef}
          className="memex-detail-title"
          type="text"
          defaultValue={title}
          style={{ ...S.title, ...(titleFocused ? S.titleFocused : {}) }}
          onFocus={() => setTitleFocused(true)}
          onBlur={(e) => { setTitleFocused(false); handleTitleSave(e.target.value.trim()); }}
          onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {type !== 'item' && <span style={S.typeBadge}>{type}</span>}
          {saveStatuses['name'] === 'saving' || saveStatuses['title'] === 'saving'
            ? <span style={{ fontSize: 11, color: 'var(--content-fg-muted)' }}>saving...</span>
            : saveStatuses['name'] === 'saved' || saveStatuses['title'] === 'saved'
            ? <span style={{ fontSize: 11, color: 'var(--accent-color, #4caf50)' }}>saved</span>
            : null
          }
        </div>
      </div>

      {/* Property panel */}
      <PropertyPanel
        properties={properties}
        saveStatuses={saveStatuses}
        onSave={handleSave}
      />

      {/* Source line */}
      <SourceLine entityData={entityData} />

      {/* Content */}
      {contentBlocks.map(([key, text]) => (
        <ContentArea key={key} content={text} fieldKey={key}
          label={contentBlocks.length > 1 ? getFieldLabel(key) : undefined}
          saveStatus={saveStatuses[key] || 'idle'}
          onSave={handleSave} />
      ))}

      {/* Relationships */}
      <RelationshipPanel
        entityId={String(entityData._entity_id || entityData.id || '')}
        plural={plural}
        relationships={relationships}
      />
    </div>
  );
}
