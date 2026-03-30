/**
 * Text Primitive Component
 * 
 * The foundational component for all text rendering. Handles overflow,
 * line clamping, typography variants, and semantic HTML — so themes
 * only need to style appearance.
 * 
 * Why a dedicated Text primitive?
 * - URLs can be very long and need truncation
 * - Titles may need line clamping
 * - Different content types have different default behaviors
 * - Themes shouldn't need to define text overflow logic
 * 
 * @example
 * ```yaml
 * - component: text
 *   props:
 *     variant: url
 *     overflow: ellipsis
 *     children: "https://example.com/very/long/path"
 * ```
 */

import React from 'react';

export interface TextProps {
  /** Text content (via children) */
  children?: React.ReactNode;
  
  /** Text content (via content prop, for YAML templates) */
  content?: string;
  
  /** Semantic variant (affects default styling) */
  variant?: 'body' | 'title' | 'subtitle' | 'caption' | 'code' | 'url' | 'label';
  
  /** Overflow behavior */
  overflow?: 'wrap' | 'truncate' | 'ellipsis';
  
  /** Maximum lines before truncation (uses CSS line-clamp) */
  maxLines?: number;
  
  /** Typography size */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  
  /** Font weight */
  weight?: 'normal' | 'medium' | 'bold';
  
  /** Text alignment */
  align?: 'left' | 'center' | 'right';
  
  /** Semantic HTML element */
  as?: 'p' | 'span' | 'h1' | 'h2' | 'h3' | 'h4' | 'label' | 'code' | 'a';
  
  /** Additional props for links */
  href?: string;
  target?: string;
  
  /** Additional CSS class */
  className?: string;
}

export function Text({
  children,
  content,
  variant = 'body',
  overflow,
  maxLines,
  size,
  weight,
  align,
  as: Element = 'span',
  href,
  target,
  className = '',
}: TextProps) {
  // For links, use 'a' element
  const Tag = href ? 'a' : Element;
  
  // Use content prop if children is not provided
  const textContent = children ?? content;
  
  // Build data attributes for CSS hooks
  const dataProps: Record<string, string | number | undefined> = {
    'data-variant': variant,
  };
  
  if (overflow) dataProps['data-overflow'] = overflow;
  if (maxLines) dataProps['data-max-lines'] = maxLines;
  if (size) dataProps['data-size'] = size;
  if (weight) dataProps['data-weight'] = weight;
  if (align) dataProps['data-align'] = align;
  
  // Inline style for alignment
  const style: React.CSSProperties = {};
  if (align) style.textAlign = align;
  
  return (
    <Tag
      className={`text ${className}`.trim()}
      style={Object.keys(style).length > 0 ? style : undefined}
      {...dataProps}
      href={href}
      target={target}
      rel={target === '_blank' ? 'noopener noreferrer' : undefined}
    >
      {textContent}
    </Tag>
  );
}

export default Text;
