import React, { useEffect, useState } from 'react'

const API = (window as any).__AGENTOS_API_BASE__ || 'http://localhost:3456'

export default function AboutPanel() {
  const [status, setStatus] = useState<{ ok: boolean; latency?: number }>({ ok: false })

  useEffect(() => {
    const start = Date.now()
    fetch(`${API}/healthz`)
      .then(r => {
        setStatus({ ok: r.ok, latency: Date.now() - start })
      })
      .catch(() => setStatus({ ok: false }))
  }, [])

  return (
    <div className="flex flex-col items-center gap-4 py-6 text-center">
      <div className="text-4xl">🖥️</div>
      <div>
        <h2 className="text-lg font-semibold text-fg">AgentOS</h2>
        <p className="text-sm text-fg-secondary mt-1">
          A personal operating system for AI agents
        </p>
      </div>
      <div className="flex flex-col gap-1 text-xs text-fg-muted">
        <div>
          Bridge:{' '}
          <span className={status.ok ? 'text-success' : 'text-urgent'}>
            {status.ok ? `connected (${status.latency}ms)` : 'disconnected'}
          </span>
        </div>
      </div>
    </div>
  )
}
