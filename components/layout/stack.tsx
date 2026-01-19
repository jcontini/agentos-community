/**
 * Stack Layout Primitive
 * 
 * Arranges children in a flex stack (horizontal or vertical).
 * Pure layout component with no behavior logic.
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
 *     - component: button
 *       props:
 *         label: "Go"
 * ```
 */

import { ReactNode, CSSProperties } from 'react';

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
  gap = '0',
  align = 'stretch',
  justify = 'start',
  wrap = false,
  fill = false,
  padding,
  children,
  className = '',
}: StackProps) {
  // Map justify values to CSS
  const justifyMap: Record<string, string> = {
    start: 'flex-start',
    center: 'center',
    end: 'flex-end',
    between: 'space-between',
    around: 'space-around',
    evenly: 'space-evenly',
  };

  // Map align values to CSS
  const alignMap: Record<string, string> = {
    start: 'flex-start',
    center: 'center',
    end: 'flex-end',
    stretch: 'stretch',
    baseline: 'baseline',
  };

  const style: CSSProperties = {
    display: 'flex',
    flexDirection: direction === 'vertical' ? 'column' : 'row',
    gap,
    alignItems: alignMap[align],
    justifyContent: justifyMap[justify],
    flexWrap: wrap ? 'wrap' : 'nowrap',
    ...(fill && { flex: 1 }),
    ...(padding && { padding }),
  };

  return (
    <div 
      className={`stack ${className}`}
      data-direction={direction}
      style={style}
    >
      {children}
    </div>
  );
}

export default Stack;
