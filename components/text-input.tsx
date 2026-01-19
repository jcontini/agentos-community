/**
 * Text Input Primitive Component
 * 
 * A controlled text input component with:
 * - Submit handling (Enter key)
 * - Clear button support
 * - Loading and disabled states
 * - Full accessibility
 * 
 * Used for search bars, URL bars, chat inputs, and forms.
 * 
 * @example
 * ```yaml
 * - component: text-input
 *   props:
 *     placeholder: "Search or enter URL"
 *     value: "{{query}}"
 *   on_submit: search
 * ```
 */

import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';

interface TextInputProps {
  /** Current value (controlled) */
  value?: string;
  /** Placeholder text */
  placeholder?: string;
  /** Disable the input */
  disabled?: boolean;
  /** Show as read-only (for display, like URL bars) */
  readOnly?: boolean;
  /** Show a border (for URL bars, etc.) */
  border?: boolean;
  /** Show loading indicator */
  loading?: boolean;
  /** Input type (text, password, email, etc.) */
  type?: 'text' | 'password' | 'email' | 'url' | 'search';
  /** Visual variant */
  variant?: 'default' | 'search' | 'url';
  /** Auto-focus on mount */
  autoFocus?: boolean;
  /** Show clear button when value is present */
  clearable?: boolean;
  /** Fired when user presses Enter */
  onSubmit?: (value: string) => void;
  /** Fired when value changes */
  onChange?: (value: string) => void;
  /** Accessibility label */
  'aria-label'?: string;
}

export function TextInput({
  value: controlledValue,
  placeholder = '',
  disabled = false,
  readOnly = false,
  border = false,
  loading = false,
  type = 'text',
  variant = 'default',
  autoFocus = false,
  clearable = false,
  onSubmit,
  onChange,
  'aria-label': ariaLabel,
}: TextInputProps) {
  // Internal state for uncontrolled usage
  const [internalValue, setInternalValue] = useState(controlledValue ?? '');
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync with controlled value
  useEffect(() => {
    if (controlledValue !== undefined) {
      setInternalValue(controlledValue);
    }
  }, [controlledValue]);

  // Auto-focus
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  const currentValue = controlledValue ?? internalValue;

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setInternalValue(newValue);
    onChange?.(newValue);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !disabled && !readOnly) {
      e.preventDefault();
      onSubmit?.(currentValue);
    }
  };

  const handleClear = () => {
    setInternalValue('');
    onChange?.('');
    inputRef.current?.focus();
  };

  const showClearButton = clearable && currentValue.length > 0 && !disabled && !readOnly;

  return (
    <div 
      className="text-input"
      data-variant={variant}
      data-disabled={disabled}
      data-readonly={readOnly}
      data-border={border}
      data-loading={loading}
    >
      {loading && (
        <span className="text-input-spinner" aria-hidden="true" />
      )}
      
      <input
        ref={inputRef}
        type={type}
        className="text-input-field"
        value={currentValue}
        placeholder={placeholder}
        disabled={disabled}
        readOnly={readOnly}
        aria-label={ariaLabel ?? placeholder}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />

      {showClearButton && (
        <button
          type="button"
          className="text-input-clear"
          onClick={handleClear}
          aria-label="Clear"
          tabIndex={-1}
        >
          ×
        </button>
      )}
    </div>
  );
}

export default TextInput;
