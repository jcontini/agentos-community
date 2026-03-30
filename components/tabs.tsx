/**
 * Tabs Component
 *
 * Two variants:
 * - `tabs` (default): Horizontal tab bar above content
 * - `sidebar`: Vertical nav on left, content on right (master-detail, full height)
 */

import React, { useState, useEffect, ReactNode, useMemo, useCallback, KeyboardEvent } from 'react';

interface TabDefinition {
  id: string;
  label: string;
  icon?: string;
  description?: string;
}

interface TabsProps {
  tabs: TabDefinition[];
  default?: string;
  activeTab?: string;
  slots?: Record<string, ReactNode>;
  variant?: 'tabs' | 'sidebar';
  className?: string;
}

export function Tabs({
  tabs,
  default: defaultTab,
  activeTab: controlledTab,
  slots = {},
  variant = 'tabs',
  className = '',
}: TabsProps) {
  const tabsArray = Array.isArray(tabs) ? tabs : [];

  const [activeTab, setActiveTab] = useState(
    controlledTab || defaultTab || tabsArray[0]?.id || ''
  );

  useEffect(() => {
    if (controlledTab && controlledTab !== activeTab) {
      setActiveTab(controlledTab);
    }
  }, [controlledTab]);

  const activePanel = slots[activeTab];
  const activeTabDef = tabsArray.find(t => t.id === activeTab);

  const selectedIndex = useMemo(() => {
    return tabsArray.findIndex(t => t.id === activeTab);
  }, [tabsArray, activeTab]);

  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const itemCount = tabsArray.length;
    if (itemCount === 0) return;

    let newIndex = selectedIndex;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        newIndex = Math.min(selectedIndex + 1, itemCount - 1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        newIndex = Math.max(selectedIndex - 1, 0);
        break;
      case 'Home':
        e.preventDefault();
        newIndex = 0;
        break;
      case 'End':
        e.preventDefault();
        newIndex = itemCount - 1;
        break;
      default:
        return;
    }
    if (newIndex !== selectedIndex) {
      setActiveTab(tabsArray[newIndex].id);
    }
  }, [tabsArray, selectedIndex, setActiveTab]);

  if (variant === 'sidebar') {
    return (
      <div className={`flex flex-row flex-1 min-h-0 bg-surface ${className}`} data-layout="sidebar">
        {/* Nav — same pattern as SidebarNav (web/src/components/SidebarNav.tsx) */}
        <nav
          className="shrink-0 border-r border-border bg-surface-muted overflow-y-auto"
          style={{ width: 176 }}
          role="listbox"
          aria-label="Navigation"
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          {tabsArray.map(tab => {
            const selected = activeTab === tab.id;
            return (
              <div
                key={tab.id}
                role="option"
                aria-selected={selected}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer select-none ${
                  selected
                    ? 'bg-highlight text-highlight-fg font-medium'
                    : 'text-fg hover:bg-surface-subtle'
                }`}
              >
                <span className="flex-1 truncate">{tab.label}</span>
              </div>
            );
          })}
        </nav>

        {/* Content */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {activeTabDef && (
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-border shrink-0">
              <h2 className="text-base font-semibold text-fg m-0">{activeTabDef.label}</h2>
              {activeTabDef.description && (
                <span className="text-xs text-fg-muted">{activeTabDef.description}</span>
              )}
            </div>
          )}
          <div className="flex-1 overflow-y-auto p-4">
            {activePanel}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`tabs ${className}`}>
      <menu role="tablist">
        {tabsArray.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </menu>
      <div
        role="tabpanel"
        id={`panel-${activeTab}`}
        aria-labelledby={activeTab}
      >
        {activePanel}
      </div>
    </div>
  );
}

export default Tabs;
