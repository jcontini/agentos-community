/**
 * Memex Browse View
 *
 * Search and browse the Memex. Self-contained component that manages
 * its own data fetching:
 *
 *   - Full-text search via POST /mem/search
 *   - Type filtering via GET /mem/{plural}
 *
 * Also accepts items/entity via props for system-initiated navigation.
 * Results rendered as a list with schema-driven display hints.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  apiFetch,
  getEntitySchema,
  getNestedValue,
  getProxiedSrc,
  getInitials,
  getColorFromString,
  inferImageVariant,
  formatValue,
} from '/ui/lib/utils.js';

// ─── Interfaces ──────────────────────────────────────────────────────────────────

interface MemexBrowseProps {
  entity?: string;
  items?: Array<Record<string, unknown>>;
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
}

// ─── Entity Types ────────────────────────────────────────────────────────────────

const ENTITY_TYPES = [
  { id: 'task', plural: 'tasks', label: 'Tasks' },
  { id: 'plan', plural: 'plans', label: 'Plans' },
  { id: 'person', plural: 'people', label: 'People' },
  { id: 'video', plural: 'videos', label: 'Videos' },
  { id: 'document', plural: 'documents', label: 'Documents' },
  { id: 'message', plural: 'messages', label: 'Messages' },
  { id: 'webpage', plural: 'webpages', label: 'Webpages' },
  { id: 'note', plural: 'notes', label: 'Notes' },
];

// ─── Styles ──────────────────────────────────────────────────────────────────────

const S = {
  container: {
    maxWidth: 780, margin: '0 auto', padding: '20px',
    color: 'var(--content-fg)',
  } as React.CSSProperties,

  searchArea: { marginBottom: 20 } as React.CSSProperties,

  searchInput: {
    width: '100%', padding: '10px 14px', fontSize: 14,
    border: '1px solid var(--content-border-subtle, rgba(128,128,128,0.2))',
    borderRadius: 8, background: 'var(--content-bg, transparent)',
    color: 'var(--content-fg)', outline: 'none', boxSizing: 'border-box' as const,
  } as React.CSSProperties,

  typeBar: { display: 'flex', flexWrap: 'wrap' as const, gap: 6, marginTop: 12 } as React.CSSProperties,

  typeChip: (active: boolean) => ({
    padding: '4px 12px', fontSize: 12, fontWeight: 500, borderRadius: 14,
    border: '1px solid var(--content-border-subtle, rgba(128,128,128,0.2))',
    background: active ? 'var(--accent-color, #6b9eff)' : 'var(--content-bg, transparent)',
    color: active ? '#fff' : 'var(--content-fg-muted)',
    cursor: 'pointer', transition: 'all 0.15s',
  } as React.CSSProperties),

  statusBar: { fontSize: 12, color: 'var(--content-fg-muted)', padding: '8px 0' } as React.CSSProperties,

  resultsList: { display: 'flex', flexDirection: 'column' as const } as React.CSSProperties,

  resultItem: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 8px',
    borderBottom: '1px solid var(--content-border-subtle, rgba(128,128,128,0.08))',
  } as React.CSSProperties,

  resultContent: {
    flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' as const, gap: 2,
  } as React.CSSProperties,

  resultPrimary: {
    fontSize: 13, fontWeight: 500, color: 'var(--content-fg)',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
  } as React.CSSProperties,

  resultSecondary: {
    fontSize: 12, color: 'var(--content-fg-muted)',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
  } as React.CSSProperties,

  resultBadge: {
    fontSize: 10, fontWeight: 500, padding: '1px 6px', borderRadius: 3,
    background: 'var(--content-bg-secondary, rgba(128,128,128,0.1))',
    color: 'var(--content-fg-muted)', textTransform: 'capitalize' as const, flexShrink: 0,
  } as React.CSSProperties,

  emptyState: {
    display: 'flex', flexDirection: 'column' as const,
    alignItems: 'center', justifyContent: 'center',
    padding: '60px 20px', gap: 8, color: 'var(--content-fg-muted)',
  } as React.CSSProperties,
};

// ─── Result Item ─────────────────────────────────────────────────────────────────

function ResultItem({ item, hints, entityType }: {
  item: Record<string, unknown>; hints: DisplayHints; entityType?: string;
}) {
  const primaryValue = getNestedValue(item, hints.primary || 'title') || item.title || item.name;
  const primaryText = primaryValue ? String(primaryValue) : 'Untitled';
  const secondaryValue = hints.secondary ? getNestedValue(item, hints.secondary) : undefined;
  const secondaryText = secondaryValue ? formatValue(secondaryValue, hints.secondary) : undefined;

  const metaParts: string[] = [];
  if (hints.meta) {
    for (const field of hints.meta) {
      const val = getNestedValue(item, field);
      if (val != null) {
        const formatted = formatValue(val, field);
        if (formatted) metaParts.push(formatted);
      }
    }
  }

  const imageRaw = hints.image ? getNestedValue(item, hints.image) : undefined;
  const imageSrc = typeof imageRaw === 'string' ? getProxiedSrc(imageRaw) : undefined;
  const variant = inferImageVariant(hints.image);
  const hasImage = Boolean(hints.image);
  const statusValue = hints.status ? getNestedValue(item, hints.status) : undefined;
  const completed = typeof statusValue === 'boolean' ? statusValue : undefined;
  const secondaryLine = [secondaryText, ...metaParts].filter(Boolean).join(' \u00B7 ');
  const itemType = entityType || (item._labels as string) || '';

  const imgSize = variant === 'avatar' ? 36 : 40;
  const imgRadius = variant === 'avatar' ? '50%' : 6;

  return (
    <div className="memex-browse-result" style={S.resultItem}>
      {hasImage && (
        imageSrc ? (
          <img src={imageSrc} alt="" loading="lazy"
            style={{ width: imgSize, height: imgSize, borderRadius: imgRadius,
              objectFit: 'cover' as const, flexShrink: 0 }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
        ) : (
          <span style={{ width: imgSize, height: imgSize, borderRadius: imgRadius,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, fontWeight: 600, color: '#fff', flexShrink: 0,
            backgroundColor: getColorFromString(primaryText) }}>
            {getInitials(primaryText)}
          </span>
        )
      )}

      <div style={S.resultContent}>
        <span style={{
          ...S.resultPrimary,
          ...(completed ? { textDecoration: 'line-through', opacity: 0.6 } : {}),
        }}>
          {primaryText}
        </span>
        {secondaryLine && <span style={S.resultSecondary}>{secondaryLine}</span>}
      </div>

      {itemType && <span style={S.resultBadge}>{itemType}</span>}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────────

export default function MemexBrowse({
  entity: propsEntity, items: propsItems, pending: propsPending, error: propsError,
}: MemexBrowseProps) {
  const [query, setQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string | null>(propsEntity || null);
  const [results, setResults] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(false);
  const [statusHint, setStatusHint] = useState('');
  const [schema, setSchema] = useState<{ display?: DisplayHints } | null>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!selectedType) { setSchema(null); return; }
    getEntitySchema(selectedType).then(setSchema);
  }, [selectedType]);

  useEffect(() => {
    if (propsItems && Array.isArray(propsItems) && propsItems.length > 0) setResults(propsItems);
  }, [propsItems]);

  const fetchByType = useCallback(async (type: string) => {
    const typeDef = ENTITY_TYPES.find(t => t.id === type);
    if (!typeDef) return;
    setLoading(true); setStatusHint('');
    try {
      const res = await apiFetch(`/mem/${typeDef.plural}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.data || []);
      setResults(items);
      setStatusHint(data.hint || `${items.length} ${typeDef.label.toLowerCase()}`);
    } catch { setResults([]); setStatusHint('Failed to load'); }
    finally { setLoading(false); }
  }, []);

  const doSearch = useCallback(async (q: string, types?: string[]) => {
    if (!q.trim() && !types?.length) return;
    setLoading(true); setStatusHint('');
    try {
      const body: Record<string, unknown> = {};
      if (q.trim()) body.query = q.trim();
      if (types?.length) body.types = types;
      const res = await apiFetch('/mem/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items = Array.isArray(data) ? data : (data.data || []);
      setResults(items);
      setStatusHint(data.hint || `${items.length} result${items.length === 1 ? '' : 's'}`);
    } catch { setResults([]); setStatusHint('Search failed'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (!query.trim() && selectedType) { fetchByType(selectedType); return; }
    if (!query.trim()) return;
    searchTimeout.current = setTimeout(() => {
      doSearch(query, selectedType ? [selectedType] : undefined);
    }, 300);
    return () => { if (searchTimeout.current) clearTimeout(searchTimeout.current); };
  }, [query, selectedType, fetchByType, doSearch]);

  useEffect(() => {
    if (selectedType && !query.trim() && results.length === 0 && !propsItems?.length) {
      fetchByType(selectedType);
    }
  }, [selectedType]);

  const handleTypeClick = (typeId: string) => {
    if (selectedType === typeId) {
      setSelectedType(null); setResults([]); setStatusHint('');
    } else {
      setSelectedType(typeId);
    }
  };

  const hints: DisplayHints = schema?.display || { primary: 'title' };
  const isLoading = loading || propsPending;
  const safeResults = Array.isArray(results) ? results : [];

  return (
    <div className="memex-browse" style={S.container}>
      <div style={S.searchArea}>
        <input
          type="text" placeholder="Search your Memex..." value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={S.searchInput} spellCheck={false} autoComplete="off" autoFocus
        />
        <div style={S.typeBar}>
          {ENTITY_TYPES.map(t => (
            <button key={t.id} style={S.typeChip(selectedType === t.id)}
              onClick={() => handleTypeClick(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {statusHint && <div style={S.statusBar}>{statusHint}</div>}

      {isLoading && (
        <div style={S.emptyState}>
          <div className="progress-bar" />
          <span style={{ fontSize: 13 }}>Searching...</span>
        </div>
      )}

      {propsError && (
        <div style={S.emptyState}>
          <span style={{ fontSize: 16, fontWeight: 500 }}>Error</span>
          <span style={{ fontSize: 13 }}>{propsError}</span>
        </div>
      )}

      {!isLoading && !propsError && safeResults.length > 0 && (
        <div style={S.resultsList}>
          {safeResults.map((item, i) => (
            <ResultItem key={(item._entity_id as string) || (item.id as string) || i}
              item={item} hints={hints}
              entityType={selectedType || (item._labels as string) || undefined} />
          ))}
        </div>
      )}

      {!isLoading && !propsError && safeResults.length === 0 && (query || selectedType) && (
        <div style={S.emptyState}>
          <span style={{ fontSize: 16, fontWeight: 500 }}>No results</span>
          <span style={{ fontSize: 13 }}>
            {query ? `Nothing found for "${query}"` : `No ${selectedType} entities yet`}
          </span>
        </div>
      )}

      {!isLoading && !propsError && safeResults.length === 0 && !query && !selectedType && (
        <div style={S.emptyState}>
          <span style={{ fontSize: 16, fontWeight: 500 }}>Your Memex</span>
          <span style={{ fontSize: 13 }}>Search for anything, or select a type to browse</span>
        </div>
      )}
    </div>
  );
}
