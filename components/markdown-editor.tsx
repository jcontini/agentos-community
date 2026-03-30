/**
 * Markdown Editor Component
 * 
 * Editable markdown with preview modes.
 * Uses textarea for editing, Markdown component for preview.
 * 
 * Modes:
 * - edit: Textarea only
 * - preview: Rendered markdown only  
 * - split: Side-by-side edit and preview
 * 
 * @example
 * ```yaml
 * - component: markdown-editor
 *   props:
 *     content: "{{content}}"
 *     mode: split
 *     onChange: handleContentChange
 * ```
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Markdown } from './markdown';

// =============================================================================
// Types
// =============================================================================

type EditorMode = 'edit' | 'preview' | 'split';

interface MarkdownEditorProps {
  /** Initial markdown content */
  content?: string;
  /** Display mode */
  mode?: EditorMode;
  /** Allow mode switching */
  allowModeSwitch?: boolean;
  /** Placeholder text for empty editor */
  placeholder?: string;
  /** Called when content changes */
  onChange?: (content: string) => void;
  /** Called when user explicitly saves (Cmd+S) */
  onSave?: (content: string) => void;
  /** Read-only mode (shows preview only, hides controls) */
  readOnly?: boolean;
  /** Additional CSS class */
  className?: string;
  /** Auto-focus the textarea on mount */
  autoFocus?: boolean;
  /** Minimum height for the editor */
  minHeight?: number;
}

// =============================================================================
// Component
// =============================================================================

export function MarkdownEditor({
  content: initialContent = '',
  mode: initialMode = 'split',
  allowModeSwitch = true,
  placeholder = 'Write markdown here...',
  onChange,
  onSave,
  readOnly = false,
  className = '',
  autoFocus = false,
  minHeight = 200,
}: MarkdownEditorProps) {
  const [content, setContent] = useState(initialContent);
  const [mode, setMode] = useState<EditorMode>(readOnly ? 'preview' : initialMode);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync with external content changes
  useEffect(() => {
    setContent(initialContent);
  }, [initialContent]);

  // Auto-focus
  useEffect(() => {
    if (autoFocus && textareaRef.current && mode !== 'preview') {
      textareaRef.current.focus();
    }
  }, [autoFocus, mode]);

  // Handle content changes
  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setContent(newContent);
    onChange?.(newContent);
  }, [onChange]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Cmd/Ctrl + S to save
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      onSave?.(content);
    }
    
    // Tab to indent
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = e.currentTarget;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      
      const newContent = content.substring(0, start) + '  ' + content.substring(end);
      setContent(newContent);
      onChange?.(newContent);
      
      // Restore cursor position
      requestAnimationFrame(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 2;
      });
    }
  }, [content, onChange, onSave]);

  // Mode switcher buttons
  const renderModeButtons = () => {
    if (!allowModeSwitch || readOnly) return null;
    
    return (
      <div className="markdown-editor-modes">
        <button
          type="button"
          className={`markdown-editor-mode-btn ${mode === 'edit' ? 'active' : ''}`}
          onClick={() => setMode('edit')}
          title="Edit mode"
        >
          Edit
        </button>
        <button
          type="button"
          className={`markdown-editor-mode-btn ${mode === 'split' ? 'active' : ''}`}
          onClick={() => setMode('split')}
          title="Split view"
        >
          Split
        </button>
        <button
          type="button"
          className={`markdown-editor-mode-btn ${mode === 'preview' ? 'active' : ''}`}
          onClick={() => setMode('preview')}
          title="Preview mode"
        >
          Preview
        </button>
      </div>
    );
  };

  // Render the textarea
  const renderEditor = () => {
    if (mode === 'preview') return null;
    
    return (
      <div className="markdown-editor-textarea-wrapper">
        <textarea
          ref={textareaRef}
          className="markdown-editor-textarea"
          value={content}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          style={{ minHeight }}
          spellCheck={false}
          aria-label="Markdown editor"
        />
      </div>
    );
  };

  // Render the preview
  const renderPreview = () => {
    if (mode === 'edit') return null;
    
    return (
      <div className="markdown-editor-preview-wrapper">
        <Markdown 
          content={content} 
          className="markdown-editor-preview"
        />
      </div>
    );
  };

  return (
    <div 
      className={`markdown-editor markdown-editor--${mode} ${className}`}
      data-mode={mode}
    >
      {/* Toolbar */}
      <div className="markdown-editor-toolbar">
        {renderModeButtons()}
      </div>
      
      {/* Content area */}
      <div className="markdown-editor-content">
        {renderEditor()}
        {mode === 'split' && <div className="markdown-editor-divider" />}
        {renderPreview()}
      </div>
    </div>
  );
}

export default MarkdownEditor;
