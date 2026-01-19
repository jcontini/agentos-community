/**
 * Scroll Area Layout Primitive
 * 
 * Creates a scrollable container with optional max height.
 * Useful for constraining content height while allowing overflow.
 * 
 * @example
 * ```yaml
 * - component: layout/scroll-area
 *   props:
 *     maxHeight: "400px"
 *   children:
 *     - component: list
 *       data:
 *         capability: message_list
 *       item_component: items/chat-bubble
 * ```
 */

import { ReactNode, CSSProperties } from 'react';

interface ScrollAreaProps {
  /** Maximum height before scrolling (CSS value) */
  maxHeight?: string;
  /** Maximum width before scrolling (CSS value) */
  maxWidth?: string;
  /** Height (CSS value) - use for fixed height containers */
  height?: string;
  /** Width (CSS value) */
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
  // Determine overflow based on direction
  const getOverflow = (): CSSProperties => {
    switch (direction) {
      case 'horizontal':
        return { overflowX: 'auto', overflowY: 'hidden' };
      case 'both':
        return { overflow: 'auto' };
      case 'vertical':
      default:
        return { overflowX: 'hidden', overflowY: 'auto' };
    }
  };

  const style: CSSProperties = {
    ...getOverflow(),
    ...(maxHeight && { maxHeight }),
    ...(maxWidth && { maxWidth }),
    ...(height && { height }),
    ...(width && { width }),
    ...(padding && { padding }),
  };

  return (
    <div 
      className={`scroll-area ${className}`}
      data-direction={direction}
      style={style}
    >
      {children}
    </div>
  );
}

export default ScrollArea;
