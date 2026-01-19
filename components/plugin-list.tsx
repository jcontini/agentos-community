/**
 * Plugin List Component
 * 
 * Displays installed plugins with enable/disable toggles.
 * Fetches plugin data directly via HTTP API.
 * 
 * @example
 * ```yaml
 * - component: plugin-list
 * ```
 */

import React, { useState, useEffect, useCallback } from 'react';

// =============================================================================
// Types
// =============================================================================

interface Plugin {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  operations: string[];
  utilities: string[];
}

interface PluginListProps {
  /** Additional CSS class */
  className?: string;
}

// =============================================================================
// API Helpers
// =============================================================================

async function fetchPlugins(): Promise<Plugin[]> {
  // Use dedicated GET endpoint (no activity logging, no WebSocket events)
  const response = await fetch('/api/plugins');
  
  if (!response.ok) {
    throw new Error(`Failed to fetch plugins: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.plugins || [];
}

async function setPluginEnabled(pluginId: string, enabled: boolean): Promise<void> {
  const action = enabled ? 'enable_plugin' : 'disable_plugin';
  
  const response = await fetch('/api/tools/call', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tool: 'Settings',
      arguments: { action, plugin: pluginId }
    })
  });
  
  if (!response.ok) {
    throw new Error(`Failed to ${action}: ${response.statusText}`);
  }
}

// =============================================================================
// Component
// =============================================================================

export function PluginList({ className = '' }: PluginListProps) {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null); // plugin id being updated

  // Fetch plugins on mount
  useEffect(() => {
    let cancelled = false;
    
    fetchPlugins()
      .then(data => {
        if (!cancelled) {
          setPlugins(data);
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
  }, []);

  // Handle toggle
  const handleToggle = useCallback(async (plugin: Plugin) => {
    const newEnabled = !plugin.enabled;
    setUpdating(plugin.id);
    
    try {
      await setPluginEnabled(plugin.id, newEnabled);
      // Update local state
      setPlugins(prev => prev.map(p => 
        p.id === plugin.id ? { ...p, enabled: newEnabled } : p
      ));
    } catch (err) {
      // Could show error toast, for now just log
      console.error('Failed to update plugin:', err);
    } finally {
      setUpdating(null);
    }
  }, []);

  // Loading state
  if (loading) {
    return (
      <div className={`plugin-list plugin-list--loading ${className}`}>
        <div className="plugin-list-loading">
          <div className="progress-bar" role="progressbar" aria-label="Loading plugins..." />
          <span className="plugin-list-loading-text">Loading plugins...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`plugin-list plugin-list--error ${className}`}>
        <div className="plugin-list-error">
          <span className="plugin-list-error-icon">⚠</span>
          <span className="plugin-list-error-text">{error}</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (plugins.length === 0) {
    return (
      <div className={`plugin-list plugin-list--empty ${className}`}>
        <div className="plugin-list-empty">
          <span className="plugin-list-empty-text">No plugins installed</span>
        </div>
      </div>
    );
  }

  // Plugin list
  return (
    <div className={`plugin-list ${className}`}>
      {plugins.map(plugin => (
        <div key={plugin.id} className="plugin-item">
          <div className="plugin-item-header">
            <label className="plugin-item-toggle">
              <input
                type="checkbox"
                checked={plugin.enabled}
                disabled={updating === plugin.id}
                onChange={() => handleToggle(plugin)}
              />
              <span className="plugin-item-name">{plugin.name}</span>
            </label>
          </div>
          {plugin.description && (
            <div className="plugin-item-description">{plugin.description}</div>
          )}
          <div className="plugin-item-meta">
            {plugin.operations.length > 0 && (
              <span className="plugin-item-operations">
                {plugin.operations.length} operation{plugin.operations.length !== 1 ? 's' : ''}
              </span>
            )}
            {plugin.utilities.length > 0 && (
              <span className="plugin-item-utilities">
                {plugin.utilities.length} utilit{plugin.utilities.length !== 1 ? 'ies' : 'y'}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default PluginList;
