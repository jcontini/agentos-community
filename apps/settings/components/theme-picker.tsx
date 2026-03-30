import React, { useEffect, useState, useCallback } from 'react'

const API = (window as any).__AGENTOS_API_BASE__ || 'http://localhost:3456'

interface ThemeInfo {
  id: string
  name: string
  description?: string
  family?: string
  has_css?: boolean
}

/**
 * Theme picker — auto-hides when there's only one theme.
 * Will reappear automatically when more native themes are added.
 */
export default function ThemePicker() {
  const [themes, setThemes] = useState<ThemeInfo[]>([])
  const [current, setCurrent] = useState<string>('')

  useEffect(() => {
    Promise.all([
      fetch(`${API}/mem/themes`).then(r => r.json()),
      fetch(`${API}/sys/settings/current_theme`).then(r => r.json()),
    ])
      .then(([themesData, settingData]) => {
        const all: ThemeInfo[] = themesData?.data || []
        setThemes(all.filter(t => t.has_css !== false))
        if (settingData?.value) setCurrent(settingData.value)
      })
      .catch(() => {})
  }, [])

  const pick = useCallback((id: string) => {
    setCurrent(id)
    fetch(`${API}/sys/settings/current_theme`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: id }),
    }).catch(() => {})
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme: id } }))
  }, [])

  if (themes.length <= 1) return null

  return (
    <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
      <legend className="font-semibold px-1.5 text-fg">Theme</legend>
      <div className="flex flex-col gap-2">
        {themes.map(t => (
          <button
            key={t.id}
            onClick={() => pick(t.id)}
            className={`bg-surface border-2 rounded px-3 py-2.5 text-left cursor-pointer transition-colors ${
              current === t.id
                ? 'border-highlight bg-highlight-bg'
                : 'border-border hover:border-border-strong'
            }`}
          >
            <div className={`font-semibold text-sm ${current === t.id ? 'text-highlight' : 'text-fg'}`}>
              {t.name}
            </div>
            {t.description && (
              <div className="text-xs text-fg-muted mt-0.5">{t.description}</div>
            )}
          </button>
        ))}
      </div>
    </fieldset>
  )
}
