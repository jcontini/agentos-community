/**
 * Entity Form Component
 * 
 * Form-style view for create/update operations.
 * Displays request parameters as form fields (read-only, showing what AI is doing).
 * Shows pending/success states for the submit action.
 * 
 * Styles defined in base.css (.entity-form-*)
 * 
 * @example
 * ```yaml
 * # Entity-form is used by Browser app (activity-based)
 * - component: entity-form
 *   props:
 *     entity: "{{activity.entity}}"
 *     operation: "{{activity.operation}}"
 *     request: "{{activity.request}}"
 *     response: "{{activity.response}}"
 *     pending: "{{activity.pending}}"
 * ```
 */

import { useState, useEffect } from 'react';

interface EntityFormProps {
  /** Entity type (e.g., 'task', 'post') */
  entity?: string;
  /** Operation (e.g., 'create', 'update') */
  operation?: string;
  /** Request parameters */
  request?: Record<string, unknown>;
  /** Response data (indicates success) */
  response?: Record<string, unknown>;
  /** Whether request is still pending */
  pending?: boolean;
  /** Error message if request failed */
  error?: string;
}

interface EntitySchema {
  properties?: Record<string, { required?: boolean }>;
  display?: {
    primary?: string;
    secondary?: string;
  };
}

/**
 * Field type hints based on common field names
 */
function getFieldType(key: string, value: unknown): 'text' | 'number' | 'boolean' | 'textarea' | 'date' {
  if (typeof value === 'boolean') return 'boolean';
  if (typeof value === 'number') return 'number';
  
  const lower = key.toLowerCase();
  if (lower.includes('date') || lower.includes('_at')) return 'date';
  if (lower.includes('description') || lower.includes('content') || lower.includes('body')) return 'textarea';
  if (lower.includes('count') || lower.includes('priority') || lower.includes('limit')) return 'number';
  
  return 'text';
}

/**
 * Get a human-readable label from field name
 */
function getFieldLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, s => s.toUpperCase())
    .trim();
}

/**
 * Format a value for display in form field
 */
function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

/**
 * Individual form field component
 */
function FormField({ 
  name, 
  value, 
  type,
  isPrimary = false,
}: { 
  name: string;
  value: unknown;
  type: 'text' | 'number' | 'boolean' | 'textarea' | 'date';
  isPrimary?: boolean;
}) {
  const label = getFieldLabel(name);
  const displayValue = formatFieldValue(value);
  
  return (
    <div className="entity-form-field">
      <label className="entity-form-field-label">
        {label}
      </label>
      
      {type === 'boolean' ? (
        <div data-component="stack" data-direction="horizontal" data-gap="sm" data-align="center">
          <span 
            data-component="checkbox" 
            data-checked={value ? 'true' : 'false'}
          >
            {value && (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </span>
          <span data-component="text">{displayValue}</span>
        </div>
      ) : type === 'textarea' ? (
        <textarea
          data-component="input"
          data-variant="textarea"
          readOnly
          value={displayValue}
        />
      ) : (
        <input
          type="text"
          data-component="input"
          data-variant={isPrimary ? 'primary' : undefined}
          readOnly
          value={displayValue}
        />
      )}
    </div>
  );
}

/**
 * Submit button component
 */
function SubmitButton({ 
  operation, 
  pending, 
  success, 
  error,
}: { 
  operation: string;
  pending: boolean;
  success: boolean;
  error?: string;
}) {
  let buttonText: string;
  let buttonState: string | undefined;
  let buttonVariant: string = 'primary';
  let buttonIcon: React.ReactNode = null;
  
  if (error) {
    buttonText = 'Failed';
    buttonState = 'error';
    buttonIcon = (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M4 4l6 6M10 4l-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    );
  } else if (pending) {
    buttonText = getActionVerb(operation, true) + '...';
    buttonState = 'loading';
    buttonIcon = (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="entity-spinner">
        <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="2" fill="none" opacity="0.3"/>
        <path d="M7 2a5 5 0 0 1 5 5" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round"/>
      </svg>
    );
  } else if (success) {
    buttonText = getActionVerb(operation, false);
    buttonState = 'success';
    buttonIcon = (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    );
  } else {
    buttonText = getActionVerb(operation, true);
  }
  
  return (
    <button 
      type="button" 
      disabled 
      data-component="button"
      data-variant={buttonVariant}
      data-state={buttonState}
    >
      {buttonIcon}
      {buttonText}
    </button>
  );
}

/**
 * Get action verb for button text
 */
function getActionVerb(operation: string, inProgress: boolean): string {
  const verbs: Record<string, [string, string]> = {
    create: ['Creating', 'Created'],
    update: ['Updating', 'Updated'],
    delete: ['Deleting', 'Deleted'],
    complete: ['Completing', 'Completed'],
    send: ['Sending', 'Sent'],
    add: ['Adding', 'Added'],
  };
  
  const [progressive, past] = verbs[operation] || ['Saving', 'Saved'];
  return inProgress ? progressive : past;
}

/**
 * Fields to exclude from display (internal/operational params)
 */
const EXCLUDED_FIELDS = ['skill', 'account', 'limit', 'offset'];

export function EntityForm({
  entity = 'item',
  operation = 'create',
  request = {},
  response,
  pending = false,
  error,
}: EntityFormProps) {
  // Fetch entity schema to know which fields are required
  const [schema, setSchema] = useState<EntitySchema | null>(null);
  
  useEffect(() => {
    if (!entity || entity === 'item') return;
    
    fetch(`/mem/_schema/${entity}`)
      .then(res => res.ok ? res.json() : null)
      .then(data => setSchema(data))
      .catch(() => setSchema(null));
  }, [entity]);
  
  // Get required fields from schema
  const requiredFields = schema?.properties
    ? Object.entries(schema.properties)
        .filter(([, prop]) => prop.required)
        .map(([key]) => key)
    : ['title', 'name'];
  
  // Get display hints from schema for field ordering
  const primaryField = schema?.display?.primary;
  const secondaryField = schema?.display?.secondary;
  
  // Filter out internal fields and sort by importance
  // Priority: primary field > secondary field > required fields > others
  const fields = Object.entries(request)
    .filter(([key]) => !EXCLUDED_FIELDS.includes(key))
    .sort(([keyA], [keyB]) => {
      // Primary field always first
      if (keyA === primaryField) return -1;
      if (keyB === primaryField) return 1;
      
      // Secondary field next
      if (keyA === secondaryField) return -1;
      if (keyB === secondaryField) return 1;
      
      // Then required fields
      const aRequired = requiredFields.includes(keyA);
      const bRequired = requiredFields.includes(keyB);
      if (aRequired && !bRequired) return -1;
      if (!aRequired && bRequired) return 1;
      
      // Default: alphabetical
      return keyA.localeCompare(keyB);
    });
  
  const success = !pending && !error && response !== undefined;
  
  const operationName = operation.charAt(0).toUpperCase() + operation.slice(1);
  const entityName = entity.charAt(0).toUpperCase() + entity.slice(1);
  
  return (
    <div className="entity-form">
      {/* Header */}
      <div className="entity-form-header">
        <h2 className="entity-form-title">
          {operationName} {entityName}
        </h2>
      </div>
      
      {/* Form content */}
      <div className="entity-form-content">
        {fields.length === 0 ? (
          <div className="entity-form-empty">
            No parameters
          </div>
        ) : (
          fields.map(([key, value]) => (
            <FormField
              key={key}
              name={key}
              value={value}
              type={getFieldType(key, value)}
              isPrimary={key === 'title' || key === 'name'}
            />
          ))
        )}
      </div>
      
      {/* Footer with submit button */}
      <div className="entity-form-footer">
        {error && (
          <span className="entity-form-error">
            {error}
          </span>
        )}
        <SubmitButton 
          operation={operation}
          pending={pending}
          success={success}
          error={error}
        />
      </div>
      
      {/* Success message */}
      {success && response && (
        <div className="entity-form-success">
          <span className="entity-form-success-name">
            {response.title || response.name || response.id || 'Item'} 
          </span>
          {' '}has been {getActionVerb(operation, false).toLowerCase()}.
        </div>
      )}
    </div>
  );
}

export default EntityForm;
