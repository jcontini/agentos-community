import React from 'react'

interface SettingsPanelProps {
  category?: string
}

const CATEGORY_INFO: Record<string, { title: string; description: string; icon: string }> = {
  features: {
    title: 'Feature Toggles',
    description: 'Enable or disable core functionality like the observer, skill auto-discovery, and background sync.',
    icon: '⚙️',
  },
  privacy: {
    title: 'Privacy Controls',
    description: 'Configure what data is shared with AI models, which skills can access your information, and data retention policies.',
    icon: '🔒',
  },
  handlers: {
    title: 'Default Handlers',
    description: 'Choose which skills handle specific content types like emails, calendar events, and web searches.',
    icon: '🔗',
  },
}

export default function SettingsPanel({ category = 'features' }: SettingsPanelProps) {
  const info = CATEGORY_INFO[category] || {
    title: category.charAt(0).toUpperCase() + category.slice(1),
    description: 'Settings for this category are not yet available.',
    icon: '📋',
  }

  return (
    <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
      <legend className="font-semibold px-1.5 text-fg">{info.title}</legend>
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <span className="text-2xl">{info.icon}</span>
        <p className="text-sm text-fg-secondary max-w-sm">{info.description}</p>
        <p className="text-xs text-fg-muted">Coming in a future update.</p>
      </div>
    </fieldset>
  )
}
