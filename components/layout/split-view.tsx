/**
 * Split View Layout Primitive
 * 
 * Divides space between two panes (horizontal or vertical split).
 * First pane has fixed size, second pane fills remaining space.
 * 
 * @example
 * ```yaml
 * - component: layout/split-view
 *   props:
 *     direction: horizontal
 *     splitAt: "300px"
 *   slots:
 *     first:
 *       component: list
 *       data:
 *         capability: message_list_conversations
 *     second:
 *       component: list
 *       data:
 *         capability: message_list
 * ```
 */

import { ReactNode, CSSProperties } from 'react';

interface SplitViewProps {
  /** Split direction: horizontal (side-by-side) or vertical (stacked) */
  direction?: 'horizontal' | 'vertical';
  /** Size of first pane (CSS value: px, %, etc.) */
  splitAt?: string;
  /** Gap between panes (CSS value) */
  gap?: string;
  /** Whether to show a divider between panes */
  showDivider?: boolean;
  /** Children array (expects exactly 2) or named slots */
  children?: [ReactNode, ReactNode];
  /** Named slots alternative to children */
  slots?: {
    first?: ReactNode;
    second?: ReactNode;
  };
  /** Additional CSS class */
  className?: string;
}

export function SplitView({
  direction = 'horizontal',
  splitAt = '50%',
  gap = '0',
  showDivider = false,
  children,
  slots,
  className = '',
}: SplitViewProps) {
  // Get panes from children array or slots
  const firstPane = slots?.first ?? children?.[0] ?? null;
  const secondPane = slots?.second ?? children?.[1] ?? null;

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: direction === 'horizontal' ? 'row' : 'column',
    gap,
    height: '100%',
    width: '100%',
  };

  const firstPaneStyle: CSSProperties = {
    flexBasis: splitAt,
    flexShrink: 0,
    flexGrow: 0,
    overflow: 'hidden',
  };

  const secondPaneStyle: CSSProperties = {
    flex: 1,
    overflow: 'hidden',
    minWidth: 0, // Prevents flex item from overflowing
    minHeight: 0,
  };

  const dividerStyle: CSSProperties = {
    flexShrink: 0,
    backgroundColor: 'var(--color-border, #333)',
    ...(direction === 'horizontal' 
      ? { width: '1px' }
      : { height: '1px' }
    ),
  };

  return (
    <div 
      className={`split-view ${className}`}
      data-direction={direction}
      style={containerStyle}
    >
      <div className="split-view-pane split-view-first" style={firstPaneStyle}>
        {firstPane}
      </div>
      
      {showDivider && (
        <div className="split-view-divider" style={dividerStyle} />
      )}
      
      <div className="split-view-pane split-view-second" style={secondPaneStyle}>
        {secondPane}
      </div>
    </div>
  );
}

export default SplitView;
