import React, { useEffect, useState, useCallback } from 'react'

const API = (window as any).__AGENTOS_API_BASE__ || 'http://localhost:3456'

type ColorMode = 'light' | 'dark' | 'auto'

const OPTIONS: { value: ColorMode; label: string; icon: string; description: string }[] = [
  { value: 'light', label: 'Light', icon: '☀️', description: 'Always use light appearance' },
  { value: 'dark', label: 'Dark', icon: '🌙', description: 'Always use dark appearance' },
  { value: 'auto', label: 'Auto', icon: '💻', description: 'Match system setting' },
]

export default function AppearanceControls() {
  const [mode, setMode] = useState<ColorMode>('auto')

  useEffect(() => {
    fetch(`${API}/sys/settings/color_mode`)
      .then(r => r.json())
      .then(d => { if (d?.value) setMode(d.value) })
      .catch(() => {})
  }, [])

  const select = useCallback((value: ColorMode) => {
    setMode(value)
    fetch(`${API}/sys/settings/color_mode`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    }).catch(() => {})
    window.dispatchEvent(new CustomEvent('color-mode-changed', { detail: { mode: value } }))
  }, [])

  return (
    <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
      <legend className="font-semibold px-1.5 text-fg">Color Mode</legend>
      <div className="flex flex-col gap-1">
        {OPTIONS.map(opt => (
          <label
            key={opt.value}
            className={`flex items-center gap-2.5 cursor-pointer rounded px-2.5 py-2 transition-colors ${
              mode === opt.value ? 'bg-highlight-bg' : 'hover:bg-surface-subtle'
            }`}
          >
            <input
              type="radio"
              name="color-mode"
              checked={mode === opt.value}
              onChange={() => select(opt.value)}
              className="accent-highlight"
            />
            <span className="text-sm">{opt.icon}</span>
            <span className="flex flex-col">
              <span className={`font-medium text-sm ${mode === opt.value ? 'text-highlight' : 'text-fg'}`}>
                {opt.label}
              </span>
              <span className="text-xs text-fg-muted">{opt.description}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
