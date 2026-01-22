/**
 * Wallpaper Picker Component
 * 
 * Displays available wallpapers organized by OS family and allows selection.
 * Persists choice to settings API and notifies the desktop to update.
 * 
 * @example
 * ```yaml
 * - component: wallpaper-picker
 *   props:
 *     family: macos  # Optional: filter to specific OS family
 * ```
 */

import React, { useState, useEffect, useCallback } from 'react';

// =============================================================================
// Types
// =============================================================================

interface WallpaperInfo {
  path: string;      // e.g., "macos/10-5.png"
  family: string;    // e.g., "macos"
  filename: string;  // e.g., "10-5.png"
}

interface WallpaperPickerProps {
  /** OS family to filter by (e.g., 'macos', 'windows'). Shows all if not specified. */
  family?: string;
  /** Additional CSS class */
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

export function WallpaperPicker({ family, className = '' }: WallpaperPickerProps) {
  const [wallpapers, setWallpapers] = useState<WallpaperInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  // Fetch wallpapers and current setting
  useEffect(() => {
    let cancelled = false;
    
    const wallpapersUrl = family ? `/api/wallpapers?family=${encodeURIComponent(family)}` : '/api/wallpapers';
    
    // Fetch both wallpapers list and current setting in parallel
    Promise.all([
      fetch(wallpapersUrl).then(r => r.ok ? r.json() : Promise.reject(new Error('Failed to load wallpapers'))),
      fetch('/api/settings/current_wallpaper').then(r => r.ok ? r.json() : null).catch(() => null),
    ])
      .then(([wallpapersData, settingData]) => {
        if (!cancelled) {
          setWallpapers(wallpapersData.wallpapers || []);
          if (settingData?.value) {
            setSelected(settingData.value);
          }
          setLoading(false);
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });
    
    return () => { cancelled = true; };
  }, [family]);

  // Handle wallpaper selection
  const handleSelect = useCallback((wallpaperPath: string) => {
    setSelected(wallpaperPath);
    
    // Save to settings API
    fetch('/api/settings/current_wallpaper', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: wallpaperPath }),
    }).catch(err => {
      console.error('Failed to save wallpaper setting:', err);
    });
    
    // Dispatch custom event so Desktop can update immediately
    // Try parent window first (for iframe contexts), then fall back to current window
    const targetWindow = window.parent !== window ? window.parent : window;
    targetWindow.dispatchEvent(new CustomEvent('wallpaper-changed', { 
      detail: { wallpaper: wallpaperPath } 
    }));
  }, []);

  // Extract display name from filename (e.g., "quantum-foam.jpg" → "Quantum Foam")
  const getDisplayName = (filename: string): string => {
    const name = filename.replace(/\.[^.]+$/, ''); // Remove extension
    return name
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Loading state
  if (loading) {
    return (
      <div className={`wallpaper-picker wallpaper-picker--loading ${className}`}>
        <div className="wallpaper-picker-loading">
          <div className="progress-bar" role="progressbar" aria-label="Loading wallpapers..." />
          <span>Loading wallpapers...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`wallpaper-picker wallpaper-picker--error ${className}`}>
        <div className="wallpaper-picker-error">
          <span>!</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  // No wallpapers
  if (wallpapers.length === 0) {
    return (
      <div className={`wallpaper-picker wallpaper-picker--empty ${className}`}>
        <div className="wallpaper-picker-empty">
          <span>No wallpapers available{family ? ` for ${family}` : ''}</span>
        </div>
      </div>
    );
  }

  // Group wallpapers by family for display
  const groupedByFamily = wallpapers.reduce((acc, wp) => {
    if (!acc[wp.family]) acc[wp.family] = [];
    acc[wp.family].push(wp);
    return acc;
  }, {} as Record<string, WallpaperInfo[]>);

  const families = Object.keys(groupedByFamily).sort();

  // Wallpaper grid
  return (
    <div className={`wallpaper-picker ${className}`}>
      {families.map(fam => (
        <div key={fam} className="wallpaper-family-group">
          {families.length > 1 && (
            <div className="wallpaper-family-header" style={{
              fontWeight: 'bold',
              marginBottom: '8px',
              textTransform: 'capitalize',
            }}>{fam}</div>
          )}
          <div className="wallpaper-family-items" style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
            gap: '8px',
          }}>
            {groupedByFamily[fam].map(wp => {
              const isSelected = wp.path === selected;
              
              return (
                <button
                  key={wp.path}
                  className={`wallpaper-item ${isSelected ? 'wallpaper-item--selected' : ''}`}
                  onClick={() => handleSelect(wp.path)}
                  type="button"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    padding: '4px',
                    border: isSelected ? '3px solid #0066cc' : '1px solid #999',
                    borderRadius: '4px',
                    background: isSelected ? '#e6f0ff' : '#fff',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s, background 0.15s',
                    minWidth: 0,
                  }}
                >
                  <img 
                    src={`/wallpapers/${wp.path}`}
                    alt={getDisplayName(wp.filename)}
                    className="wallpaper-item-thumbnail"
                    loading="lazy"
                    style={{
                      width: '100%',
                      height: '60px',
                      objectFit: 'cover',
                      borderRadius: '2px',
                    }}
                  />
                  <span className="wallpaper-item-name" style={{
                    marginTop: '4px',
                    fontSize: '10px',
                    textAlign: 'center',
                    wordBreak: 'break-word',
                    lineHeight: 1.2,
                  }}>
                    {getDisplayName(wp.filename)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default WallpaperPicker;
