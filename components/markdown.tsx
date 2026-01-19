/**
 * Markdown Primitive Component
 * 
 * Renders markdown content as styled HTML.
 * Uses a simple built-in parser for basic markdown.
 * Themes style the rendered output via CSS.
 * 
 * Supports:
 * - Headings (h1-h6)
 * - Bold, italic, code
 * - Links
 * - Lists (ordered and unordered)
 * - Blockquotes
 * - Code blocks
 * - Horizontal rules
 * 
 * @example
 * ```yaml
 * - component: markdown
 *   data:
 *     capability: web_read
 *     params:
 *       url: "{{params.url}}"
 *   props:
 *     content: "{{content}}"
 * ```
 */

interface MarkdownProps {
  /** Markdown content to render */
  content?: string;
  /** Additional CSS class */
  className?: string;
  /** Show loading state */
  loading?: boolean;
  /** Error message */
  error?: string;
}

export function Markdown({
  content = '',
  className = '',
  loading = false,
  error,
}: MarkdownProps) {
  if (loading) {
    return (
      <div className={`markdown markdown--loading ${className}`} aria-busy="true">
        <div className="markdown-loading">
          <span className="markdown-loading-text">Loading content...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`markdown markdown--error ${className}`} role="alert">
        <div className="markdown-error">
          <span className="markdown-error-icon" aria-hidden="true">⚠</span>
          <span className="markdown-error-text">{error}</span>
        </div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className={`markdown markdown--empty ${className}`}>
        <div className="markdown-empty">
          <span className="markdown-empty-text">No content</span>
        </div>
      </div>
    );
  }

  const html = renderMarkdown(content);

  return (
    <div 
      className={`markdown ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/**
 * Simple markdown renderer
 * Converts basic markdown syntax to HTML
 */
function renderMarkdown(content: string): string {
  let html = escapeHtml(content);

  // Code blocks (must be first to prevent inner parsing)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const langAttr = lang ? ` data-language="${lang}"` : '';
    return `<pre class="markdown-code-block"${langAttr}><code>${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="markdown-code">$1</code>');

  // Headings
  html = html.replace(/^###### (.+)$/gm, '<h6 class="markdown-h6">$1</h6>');
  html = html.replace(/^##### (.+)$/gm, '<h5 class="markdown-h5">$1</h5>');
  html = html.replace(/^#### (.+)$/gm, '<h4 class="markdown-h4">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3 class="markdown-h3">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="markdown-h2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="markdown-h1">$1</h1>');

  // Bold and italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/___(.+?)___/g, '<strong><em>$1</em></strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  html = html.replace(/_(.+?)_/g, '<em>$1</em>');

  // Strikethrough
  html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="markdown-link" target="_blank" rel="noopener">$1</a>');

  // Images
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="markdown-image" />');

  // Horizontal rules
  html = html.replace(/^(?:---|\*\*\*|___)\s*$/gm, '<hr class="markdown-hr" />');

  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote class="markdown-blockquote">$1</blockquote>');

  // Unordered lists
  html = html.replace(/^[\*\-] (.+)$/gm, '<li class="markdown-li">$1</li>');
  html = html.replace(/(<li class="markdown-li">.*<\/li>\n?)+/g, '<ul class="markdown-ul">$&</ul>');

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="markdown-li-ordered">$1</li>');
  html = html.replace(/(<li class="markdown-li-ordered">.*<\/li>\n?)+/g, '<ol class="markdown-ol">$&</ol>');

  // Paragraphs (lines not already wrapped)
  html = html.replace(/^(?!<[huplo]|<bl|<hr|<pre|<li)(.+)$/gm, '<p class="markdown-p">$1</p>');

  // Clean up extra newlines
  html = html.replace(/\n\n+/g, '\n');

  return html;
}

/**
 * Escape HTML entities to prevent XSS
 */
function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, char => map[char]);
}

export default Markdown;
