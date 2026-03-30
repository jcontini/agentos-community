/**
 * Content Primitive Component
 * 
 * Smart content renderer that dispatches to the appropriate renderer
 * based on content type. Used primarily for curl/raw HTTP responses
 * where the content type isn't known until runtime.
 * 
 * Supported content types:
 * - application/json → JSON syntax highlighting
 * - text/html → Markdown renderer (HTML passthrough)
 * - text/markdown → Markdown renderer
 * - text/plain → Plain text
 * - image/* → Image display
 * 
 * @example
 * ```yaml
 * - component: content
 *   props:
 *     data: "{{activity.response.content}}"
 *     type: "{{activity.response.content_type}}"
 * ```
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';

interface ContentProps {
  /** The content to render */
  data?: string;
  /** MIME content type (e.g., "application/json", "text/html") */
  type?: string;
  /** URL for images (when type is image/*) */
  url?: string;
  /** Additional CSS class */
  className?: string;
  /** Show loading state */
  loading?: boolean;
  /** Error message */
  error?: string;
}

export function Content({
  data = '',
  type = 'text/plain',
  url,
  className = '',
  loading = false,
  error,
}: ContentProps) {
  if (loading) {
    return (
      <div className={`content content--loading ${className}`} aria-busy="true">
        <div className="content-loading">
          <div className="progress-bar" role="progressbar" aria-label="Loading content..." />
          <span className="content-loading-text">Loading content...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`content content--error ${className}`} role="alert">
        <div className="content-error">
          <span className="content-error-icon" aria-hidden="true">⚠</span>
          <span className="content-error-text">{error}</span>
        </div>
      </div>
    );
  }

  // Normalize content type (strip charset, etc.)
  const normalizedType = type.toLowerCase().split(';')[0].trim();

  // Dispatch to appropriate renderer
  if (normalizedType === 'application/json' || normalizedType.endsWith('+json')) {
    return <JsonContent data={data} className={className} />;
  }

  if (normalizedType.startsWith('image/')) {
    return <ImageContent url={url} data={data} type={normalizedType} className={className} />;
  }

  if (normalizedType === 'text/html') {
    // Render HTML with sanitization (strip CSS/JS, add target="_blank" to links, same-domain images only)
    return <HtmlContent data={data} sourceUrl={url} className={className} />;
  }

  if (normalizedType === 'text/markdown') {
    return <MarkdownContent data={data} className={className} />;
  }

  // Default: plain text
  return <TextContent data={data} className={className} />;
}

/**
 * JSON Content Renderer
 * Pretty-prints JSON with syntax highlighting
 */
function JsonContent({ data, className }: { data: string; className: string }) {
  let formatted: React.ReactNode;
  
  try {
    const parsed = JSON.parse(data);
    formatted = syntaxHighlight(JSON.stringify(parsed, null, 2));
  } catch {
    // If not valid JSON, show as-is with error indicator
    return (
      <div className={`content content--json content--invalid ${className}`}>
        <div className="content-json-error">Invalid JSON</div>
        <pre className="content-json-raw">{data}</pre>
      </div>
    );
  }

  return (
    <div className={`content content--json ${className}`}>
      <pre className="content-json">{formatted}</pre>
    </div>
  );
}

/**
 * Syntax highlight JSON
 * Returns React elements with appropriate classes for styling
 */
function syntaxHighlight(json: string): React.ReactNode[] {
  const elements: React.ReactNode[] = [];
  let key = 0;
  
  // Regex to match JSON tokens
  const regex = /("(?:\\.|[^"\\])*"(?=\s*:))|("(?:\\.|[^"\\])*")|(\b(?:true|false|null)\b)|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)|([{}\[\],:])|(\s+)/g;
  
  let match;
  while ((match = regex.exec(json)) !== null) {
    const [token] = match;
    
    if (match[1]) {
      // Key (string followed by colon)
      elements.push(<span key={key++} className="json-key">{token}</span>);
    } else if (match[2]) {
      // String value
      elements.push(<span key={key++} className="json-string">{token}</span>);
    } else if (match[3]) {
      // Boolean or null
      elements.push(<span key={key++} className="json-boolean">{token}</span>);
    } else if (match[4]) {
      // Number
      elements.push(<span key={key++} className="json-number">{token}</span>);
    } else if (match[5]) {
      // Punctuation
      elements.push(<span key={key++} className="json-punctuation">{token}</span>);
    } else if (match[6]) {
      // Whitespace (preserve formatting)
      elements.push(<span key={key++}>{token}</span>);
    }
  }
  
  return elements;
}

/**
 * Image Content Renderer
 */
function ImageContent({ 
  url, 
  data, 
  type, 
  className 
}: { 
  url?: string; 
  data: string; 
  type: string; 
  className: string;
}) {
  // If we have a URL, use it directly
  // If we have base64 data, construct a data URI
  const src = url || (data ? `data:${type};base64,${data}` : undefined);
  
  if (!src) {
    return (
      <div className={`content content--image content--empty ${className}`}>
        <span>No image data</span>
      </div>
    );
  }

  return (
    <div className={`content content--image ${className}`}>
      <img src={src} alt="" className="content-image" />
    </div>
  );
}

/**
 * HTML Content Renderer
 * Sanitizes and renders HTML (strips CSS/JS, adds target="_blank" to links, same-domain images only)
 */
function HtmlContent({ data, sourceUrl, className }: { data: string; sourceUrl?: string; className: string }) {
  const sanitized = sanitizeHtml(data, sourceUrl);
  return (
    <div 
      className={`content content--html ${className}`}
      dangerouslySetInnerHTML={{ __html: sanitized }}
    />
  );
}

/**
 * Sanitize HTML for safe rendering
 * - Strips: <style>, <script>, <head>, <link>
 * - Removes: inline style attributes
 * - Adds: target="_blank" to all links
 * - Only allows images from the same domain (blocks third-party tracking)
 */
function sanitizeHtml(html: string, sourceUrl?: string): string {
  let content = html;
  
  // Extract the allowed domain from the source URL
  let allowedDomain: string | null = null;
  if (sourceUrl) {
    try {
      const url = new URL(sourceUrl);
      allowedDomain = url.hostname;
    } catch {
      // Invalid URL, no images will be allowed
    }
  }
  
  // Remove everything in <head>
  content = content.replace(/<head[^>]*>[\s\S]*?<\/head>/gi, '');
  
  // Remove <style> tags and contents
  content = content.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');
  
  // Remove <script> tags and contents
  content = content.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '');
  
  // Remove <link> tags (external stylesheets)
  content = content.replace(/<link[^>]*>/gi, '');
  
  // Extract body content if present
  const bodyMatch = content.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch) {
    content = bodyMatch[1];
  }
  
  // Remove html/body wrapper tags
  content = content.replace(/<\/?html[^>]*>/gi, '');
  content = content.replace(/<\/?body[^>]*>/gi, '');
  
  // Remove inline style attributes
  content = content.replace(/\s+style\s*=\s*"[^"]*"/gi, '');
  content = content.replace(/\s+style\s*=\s*'[^']*'/gi, '');
  
  // Filter images: only allow same-domain images
  content = content.replace(/<img\s+([^>]*)>/gi, (match, attrs) => {
    // Extract src attribute
    const srcMatch = attrs.match(/src\s*=\s*["']([^"']*)["']/i);
    if (!srcMatch) {
      return ''; // No src, remove image
    }
    
    const imgSrc = srcMatch[1];
    
    // Allow relative URLs (same domain)
    if (imgSrc.startsWith('/') || imgSrc.startsWith('./') || imgSrc.startsWith('../')) {
      // Convert relative URL to absolute using source domain
      if (allowedDomain && sourceUrl) {
        try {
          const absoluteUrl = new URL(imgSrc, sourceUrl).href;
          return `<img ${attrs.replace(srcMatch[0], `src="${absoluteUrl}"`)}>`;
        } catch {
          return ''; // Invalid URL
        }
      }
      return match; // Keep as-is if no source URL
    }
    
    // Also handle URLs without leading slash (like "y18.svg")
    if (!imgSrc.includes('://')) {
      // Relative URL without path prefix - convert to absolute
      if (allowedDomain && sourceUrl) {
        try {
          const absoluteUrl = new URL(imgSrc, sourceUrl).href;
          return `<img ${attrs.replace(srcMatch[0], `src="${absoluteUrl}"`)}>`;
        } catch {
          return ''; // Invalid URL
        }
      }
      return match;
    }
    
    // Allow data URIs
    if (imgSrc.startsWith('data:')) {
      return match;
    }
    
    // Check if image is from the same domain
    if (allowedDomain) {
      try {
        const imgUrl = new URL(imgSrc);
        if (imgUrl.hostname === allowedDomain || imgUrl.hostname.endsWith('.' + allowedDomain)) {
          return match; // Same domain, allow
        }
      } catch {
        // Invalid URL, remove
      }
    }
    
    // Different domain - remove the image
    return '';
  });
  
  // Add target="_blank" and rel="noopener" to all links
  content = content.replace(/<a\s+([^>]*href[^>]*)>/gi, (match, attrs) => {
    // Remove any existing target attribute
    attrs = attrs.replace(/\s*target\s*=\s*["'][^"']*["']/gi, '');
    // Remove any existing rel attribute (we'll add our own)
    attrs = attrs.replace(/\s*rel\s*=\s*["'][^"']*["']/gi, '');
    return `<a ${attrs} target="_blank" rel="noopener noreferrer">`;
  });
  
  return content.trim();
}

/**
 * Markdown Content Renderer
 * Uses react-markdown for proper CommonMark-compliant parsing
 */
function MarkdownContent({ data, className }: { data: string; className: string }) {
  return (
    <div className={`content content--markdown markdown ${className}`}>
      <ReactMarkdown
        components={{
          // Open links in new tab
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          // Style images
          img: ({ src, alt }) => (
            <img 
              src={src} 
              alt={alt || ''} 
              className="markdown-image"
            />
          ),
        }}
      >
        {data}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Plain Text Content Renderer
 */
function TextContent({ data, className }: { data: string; className: string }) {
  return (
    <div className={`content content--text ${className}`}>
      <pre className="content-text">{data}</pre>
    </div>
  );
}

export default Content;
