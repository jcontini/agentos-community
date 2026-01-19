/**
 * Toggle Component
 * 
 * A checkbox toggle with label using OS 9 styling.
 * Follows macOS 9 pattern: main label + optional description below.
 * 
 * @example
 * ```yaml
 * # Simple toggle
 * - component: toggle
 *   props:
 *     label: Enable activity logging
 *     checked: "{{settings.logging_enabled}}"
 *   on_change:
 *     action: settings.set
 *     params:
 *       key: logging_enabled
 * 
 * # With description (macOS 9 pattern)
 * - component: toggle
 *   props:
 *     label: Simple Finder
 *     description: Provides only the essential features and commands
 *     checked: "{{settings.simple_finder}}"
 * ```
 * 
 * Theme CSS:
 * ```css
 * input[type=checkbox] { ... OS 9 checkbox styling ... }
 * .toggle-description { ... smaller text below label ... }
 * ```
 */

import React from 'react';

interface ToggleProps {
  /** Label text displayed next to the checkbox */
  label: string;
  /** Optional description shown below the label (smaller text) */
  description?: string;
  /** Whether the toggle is checked */
  checked?: boolean;
  /** Disable the toggle */
  disabled?: boolean;
  /** Fired when toggle state changes (receives new checked value) */
  onChange?: (checked: boolean) => void;
  /** Additional CSS class */
  className?: string;
}

export function Toggle({
  label,
  description,
  checked = false,
  disabled = false,
  onChange,
  className = '',
}: ToggleProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.checked);
  };

  return (
    <div className={`toggle ${className}`} data-disabled={disabled || undefined}>
      <label className="toggle-row">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={handleChange}
        />
        <span className="toggle-label">{label}</span>
      </label>
      {description && (
        <div className="toggle-description">{description}</div>
      )}
    </div>
  );
}

export default Toggle;
