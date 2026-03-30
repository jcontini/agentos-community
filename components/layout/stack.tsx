/**
 * Stack Layout Primitive
 * 
 * Arranges children in a flex stack (horizontal or vertical).
 * Uses CSS classes and custom properties so themes can style it.
 * 
 * @example
 * ```yaml
 * - component: layout/stack
 *   props:
 *     direction: horizontal
 *     gap: "8px"
 *     align: center
 *   children:
 *     - component: text-input
 *       props:
 *         placeholder: "Search..."
 * ```
 * 
 * Theme CSS example:
 * ```css
 * .stack { display: flex; gap: var(--stack-gap, 0); }
 * .stack[data-direction="vertical"] { flex-direction: column; }
 * .stack[data-direction="horizontal"] { flex-direction: row; }
 * .stack[data-align="center"] { align-items: center; }
 * .stack[data-justify="between"] { justify-content: space-between; }
 * ```
 */

import React, { ReactNode, CSSProperties } from 'react';

interface StackProps {
  /** Stack direction */
  direction?: 'horizontal' | 'vertical';
  /** Gap between items (CSS value) */
  gap?: string;
  /** Cross-axis alignment */
  align?: 'start' | 'center' | 'end' | 'stretch' | 'baseline';
  /** Main-axis distribution */
  justify?: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly';
  /** Whether items should wrap */
  wrap?: boolean;
  /** Whether to fill available space */
  fill?: boolean;
  /** Padding (CSS value) */
  padding?: string;
  /** Child components */
  children?: ReactNode;
  /** Additional CSS class */
  className?: string;
}

export function Stack({
  direction = 'vertical',
  gap,
  align,
  justify,
  wrap = false,
  fill = false,
  padding,
  children,
  className = '',
}: StackProps) {
  // Pass layout values as CSS custom properties for theme control
  const style: CSSProperties = {
    ...(gap && { '--stack-gap': gap }),
    ...(padding && { '--stack-padding': padding }),
  } as CSSProperties;

  return (
    <div 
      className={`stack ${className}`}
      data-direction={direction}
      data-align={align}
      data-justify={justify}
      data-wrap={wrap || undefined}
      data-fill={fill || undefined}
      style={Object.keys(style).length > 0 ? style : undefined}
    >
      {children}
    </div>
  );
}

export default Stack;
