/**
 * Action Bar Component
 *
 * Renders entity-specific action buttons and toggles in the Browser toolbar.
 * Dynamically adapts based on the current entity's actions from the schema.
 *
 * Two kinds of controls:
 * - "action" → button (e.g., Delete). Calls POST /mem/{plural}/{id}/{action}
 * - "toggle" → checkbox (e.g., Completed, Archived). Reads current state from
 *   entity data via property path, toggles between paired operations.
 */

import React, { useState, useCallback } from 'react';

interface EntityAction {
  id: string;
  kind: 'action' | 'toggle';
  label: string;
  requires_id: boolean;
  confirm?: boolean;
  property?: string;
  pair?: string;
}

interface ActionBarProps {
  /** Actions from the entity schema */
  actions?: EntityAction[];
  /** Current entity type (e.g., "task") */
  entityType?: string;
  /** Plural form for REST URLs (e.g., "tasks") */
  plural?: string;
  /** Current entity ID (from detail view or selected item) */
  entityId?: string;
  /** Current entity data (for reading toggle state) */
  entityData?: Record<string, unknown>;
}

/** Read a nested property by dot-path (e.g., "data.completed" → obj.data.completed) */
function readProperty(obj: Record<string, unknown> | undefined, path: string): unknown {
  if (!obj) return undefined;
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

export function ActionBar({
  actions,
  entityType,
  plural,
  entityId,
  entityData,
}: ActionBarProps) {
  const [executing, setExecuting] = useState<string | null>(null);

  const executeAction = useCallback(async (actionId: string, requiresId: boolean) => {
    if (!plural) return;
    setExecuting(actionId);
    try {
      const url = requiresId && entityId
        ? `/mem/${plural}/${entityId}/${actionId}`
        : `/mem/${plural}`;
      await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Agent': 'webui' },
        body: JSON.stringify({}),
      });
    } catch (err) {
      console.error(`[ActionBar] Failed to execute ${actionId}:`, err);
    } finally {
      setExecuting(null);
    }
  }, [plural, entityId]);

  if (!actions || actions.length === 0 || !entityType) return null;

  const relevantActions = actions.filter(a =>
    !a.requires_id || (a.requires_id && entityId)
  );

  if (relevantActions.length === 0) return null;

  return (
    <div className="action-bar">
      {relevantActions.map((action) => {
        if (action.kind === 'toggle') {
          const currentValue = action.property
            ? !!readProperty(entityData, action.property)
            : false;
          const isExecuting = executing === action.id || executing === action.pair;

          const handleToggle = () => {
            if (isExecuting) return;
            const opToCall = currentValue && action.pair ? action.pair : action.id;
            executeAction(opToCall, action.requires_id);
          };

          return (
            <label
              key={action.id}
              className="action-bar-toggle"
              data-checked={currentValue}
              data-executing={isExecuting}
            >
              <input
                type="checkbox"
                checked={currentValue}
                onChange={handleToggle}
                disabled={isExecuting}
              />
              <span className="action-bar-toggle-label">{action.label}</span>
            </label>
          );
        }

        const isExecuting = executing === action.id;
        const handleClick = () => {
          if (isExecuting) return;
          if (action.confirm && !window.confirm(`${action.label} this ${entityType}?`)) return;
          executeAction(action.id, action.requires_id);
        };

        return (
          <button
            key={action.id}
            className="action-bar-button"
            onClick={handleClick}
            disabled={isExecuting}
            data-action={action.id}
            data-executing={isExecuting}
          >
            {action.label}
          </button>
        );
      })}
    </div>
  );
}

export default ActionBar;
