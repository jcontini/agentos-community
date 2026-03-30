import React from 'react'

export default function WebDefaults() {
  return (
    <fieldset className="border border-border-strong rounded px-4 py-3 m-0">
      <legend className="font-semibold px-1.5 text-fg">Web Browser Defaults</legend>
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <span className="text-2xl">🌐</span>
        <p className="text-sm text-fg-secondary max-w-sm">
          Set your default search engine, home page, and which skills handle web content.
        </p>
        <p className="text-xs text-fg-muted">Coming in a future update.</p>
      </div>
    </fieldset>
  )
}
