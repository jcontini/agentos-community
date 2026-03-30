import React, { useEffect, useState, useCallback } from 'react'

const API = (window as any).__AGENTOS_API_BASE__ || 'http://localhost:3456'

interface WallpaperInfo {
  id: string
  name: string
  path?: string
  family?: string
}

export default function WallpaperPicker() {
  const [wallpapers, setWallpapers] = useState<WallpaperInfo[]>([])
  const [current, setCurrent] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch(`${API}/graph`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: 'read', params: { tags: 'wallpaper' } }),
      }).then(r => r.json()),
      fetch(`${API}/sys/settings/current_wallpaper`).then(r => r.json()),
    ])
      .then(([graphData, settingData]) => {
        const entities = graphData?.entities || graphData?.data || []
        const mapped: WallpaperInfo[] = entities.map((e: any) => ({
          id: e.id || e.address,
          name: e.name || e.vals?.filename || 'Wallpaper',
          path: e.vals?.path || e.path,
          family: e.vals?.family || e.family,
        }))
        setWallpapers(mapped)
        if (settingData?.value) setCurrent(settingData.value)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  const pick = useCallback((path: string) => {
    setCurrent(path)
    fetch(`${API}/sys/settings/current_wallpaper`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: path }),
    }).catch(() => {})
    window.dispatchEvent(new CustomEvent('wallpaper-changed', { detail: { wallpaper: path } }))
  }, [])

  const clearWallpaper = useCallback(() => {
    setCurrent('')
    fetch(`${API}/sys/settings/current_wallpaper`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: '' }),
    }).catch(() => {})
    window.dispatchEvent(new CustomEvent('wallpaper-changed', { detail: { wallpaper: '' } }))
  }, [])

  if (loading) {
    return (
      <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
        <legend className="font-semibold px-1.5 text-fg">Desktop Background</legend>
        <div className="text-sm text-fg-muted py-4 text-center">Loading wallpapers…</div>
      </fieldset>
    )
  }

  return (
    <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
      <legend className="font-semibold px-1.5 text-fg">Desktop Background</legend>
      <div className="flex flex-col gap-3">
        <button
          onClick={clearWallpaper}
          className={`bg-surface border-2 rounded px-3 py-2 text-left cursor-pointer text-sm transition-colors ${
            !current ? 'border-highlight bg-highlight-bg text-highlight' : 'border-border hover:border-border-strong text-fg'
          }`}
        >
          None (solid color)
        </button>
        {wallpapers.length > 0 ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-2">
            {wallpapers.map(w => (
              <button
                key={w.path || w.id}
                onClick={() => w.path && pick(w.path)}
                className={`border-2 rounded overflow-hidden cursor-pointer transition-colors ${
                  current === w.path
                    ? 'border-highlight'
                    : 'border-border hover:border-border-strong'
                }`}
              >
                {w.path && (
                  <img
                    src={`${API}/ui/wallpapers/${w.path}`}
                    alt={w.name}
                    className="w-full aspect-video object-cover"
                  />
                )}
                <div className="px-2 py-1 text-xs text-fg-muted truncate">{w.name}</div>
              </button>
            ))}
          </div>
        ) : (
          <div className="text-sm text-fg-muted text-center py-2">
            No wallpapers found. Add images to <code className="text-xs bg-surface-inset px-1 rounded">~/.agentos/installed/wallpapers/</code>
          </div>
        )}
      </div>
    </fieldset>
  )
}
