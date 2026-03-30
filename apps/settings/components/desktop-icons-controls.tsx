import React, { useEffect, useState, useCallback } from 'react'

const API = (window as any).__AGENTOS_API_BASE__ || 'http://localhost:3456'

const CORNERS = [
  { value: 'top-right', label: 'Top Right' },
  { value: 'top-left', label: 'Top Left' },
  { value: 'bottom-right', label: 'Bottom Right' },
  { value: 'bottom-left', label: 'Bottom Left' },
]

const SIZES = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
]

const SPACINGS = [
  { value: 'compact', label: 'Compact' },
  { value: 'normal', label: 'Normal' },
  { value: 'relaxed', label: 'Relaxed' },
]

interface IconSettings {
  icon_starting_corner: string
  icon_size: string
  icon_spacing: string
}

const DEFAULTS: IconSettings = {
  icon_starting_corner: 'top-right',
  icon_size: 'medium',
  icon_spacing: 'normal',
}

export default function DesktopIconsControls() {
  const [settings, setSettings] = useState<IconSettings>(DEFAULTS)

  useEffect(() => {
    Promise.all(
      Object.keys(DEFAULTS).map(key =>
        fetch(`${API}/sys/settings/${key}`)
          .then(r => r.json())
          .then(d => [key, d?.value] as [string, string])
      )
    )
      .then(entries => {
        const updates: Partial<IconSettings> = {}
        for (const [k, v] of entries) {
          if (v) (updates as any)[k] = v
        }
        setSettings(prev => ({ ...prev, ...updates }))
      })
      .catch(() => {})
  }, [])

  const update = useCallback((key: keyof IconSettings, value: string) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    fetch(`${API}/sys/settings/${key}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    }).catch(() => {})
    window.dispatchEvent(
      new CustomEvent('icon-settings-changed', { detail: { key, value } })
    )
  }, [])

  return (
    <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
      <legend className="font-semibold px-1.5 text-fg">Desktop Icons</legend>
      <div className="flex flex-col gap-2.5">
        <Row label="Starting corner">
          <SelectRow
            options={CORNERS}
            value={settings.icon_starting_corner}
            onChange={v => update('icon_starting_corner', v)}
          />
        </Row>
        <Row label="Icon size">
          <SelectRow
            options={SIZES}
            value={settings.icon_size}
            onChange={v => update('icon_size', v)}
          />
        </Row>
        <Row label="Spacing">
          <SelectRow
            options={SPACINGS}
            value={settings.icon_spacing}
            onChange={v => update('icon_spacing', v)}
          />
        </Row>
      </div>
    </fieldset>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm font-medium text-fg min-w-28">{label}</span>
      {children}
    </div>
  )
}

function SelectRow({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select
      data-component="select"
      data-size="sm"
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-auto min-w-32"
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}
