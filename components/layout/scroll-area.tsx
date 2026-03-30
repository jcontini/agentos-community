/**
 * Scroll Area Layout Primitive
 * 
 * Creates a scrollable container with configurable dimensions.
 * Uses CSS classes and custom properties so themes can style scrollbars.
 * 
 * @example
 * ```yaml
 * - component: layout/scroll-area
 *   props:
 *     maxHeight: "400px"
 *     direction: vertical
 *   children:
 *     - component: list
 *       data:
 *         capability: message_list
 * ```
 * 
 * Theme CSS example:
 * ```css
 * .scroll-area { 
 *   max-height: var(--scroll-max-height, 100%);
 *   max-width: var(--scroll-max-width);
 * }
 * .scroll-area[data-direction="vertical"] { overflow-y: auto; overflow-x: hidden; }
 * .scroll-area[data-direction="horizontal"] { overflow-x: auto; overflow-y: hidden; }
 * .scroll-area[data-direction="both"] { overflow: auto; }
 * 
 * // Custom scrollbar styling
 * .scroll-area::-webkit-scrollbar { width: 8px; }
 * .scroll-area::-webkit-scrollbar-thumb { background: var(--color-border); }
 * ```
 */

import React, { ReactNode, CSSProperties } from 'react';

interface ScrollAreaProps {
  /** Maximum height before scrolling (CSS value) */
  maxHeight?: string;
  /** Maximum width before scrolling (CSS value) */
  maxWidth?: string;
  /** Fixed height (CSS value) */
  height?: string;
  /** Fixed width (CSS value) */
  width?: string;
  /** Scroll direction: vertical, horizontal, or both */
  direction?: 'vertical' | 'horizontal' | 'both';
  /** Padding inside the scroll area (CSS value) */
  padding?: string;
  /** Child components */
  children?: ReactNode;
  /** Additional CSS class */
  className?: string;
}

export function ScrollArea({
  maxHeight,
  maxWidth,
  height,
  width,
  direction = 'vertical',
  padding,
  children,
  className = '',
}: ScrollAreaProps) {
  // Pass dimension values as CSS custom properties for theme control
  const style: CSSProperties = {
    ...(maxHeight && { '--scroll-max-height': maxHeight }),
    ...(maxWidth && { '--scroll-max-width': maxWidth }),
    ...(height && { '--scroll-height': height }),
    ...(width && { '--scroll-width': width }),
    ...(padding && { '--scroll-padding': padding }),
  } as CSSProperties;

  return (
    <div 
      className={`scroll-area ${className}`}
      data-direction={direction}
      style={Object.keys(style).length > 0 ? style : undefined}
    >
      {children}
    </div>
  );
}

export default ScrollArea;
