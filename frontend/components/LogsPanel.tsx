'use client'

import React, { useEffect, useRef, useState } from 'react'

interface Props {
  apiUrl: string
  theme: 'dark' | 'light'
  onClose: () => void
}

export default function LogsPanel({ apiUrl, theme, onClose }: Props) {
  const [lines, setLines] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setInterval>
    const load = () => {
      fetch(`${apiUrl}/api/logs`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((d) => {
          if (!cancelled) {
            setLines(d.lines || [])
            setError(null)
            setLoading(false)
          }
        })
        .catch((e) => {
          if (!cancelled) {
            setError(String((e as Error).message || e))
            setLoading(false)
          }
        })
    }
    load()
    timer = setInterval(load, 2000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [apiUrl])

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight })
  }, [lines])

  const mono = 'font-mono text-xs leading-5'
  return (
    <div className={`flex flex-col h-full ${theme === 'dark' ? 'text-slate-100' : 'text-gray-900'}`}>
      <div className={`p-4 flex items-center justify-between ${theme === 'dark' ? 'border-slate-700' : 'border-gray-200'} border-b`}>
        <h2 className="font-semibold text-base">
          Runtime Logs
          <span className="ml-2 align-middle inline-block w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: '#22c55e' }} />
        </h2>
        <button onClick={onClose} className="opacity-60 hover:opacity-100" title="Close logs">✕</button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 bg-black/90" ref={bodyRef}>
        {error && (
          <div className="text-red-400 text-xs p-2 mb-2 rounded" style={{ backgroundColor: 'rgba(239,68,68,0.1)' }}>
            Cannot reach /api/logs — {error}. Is the backend running?
          </div>
        )}
        {loading && !lines.length && !error && <div className="text-slate-400 text-xs">Loading logs…</div>}
        {lines.length === 0 && !loading && !error && (
          <div className="text-slate-500 text-xs">No log entries yet (server logs land in private/runtime/ via start.sh).</div>
        )}
        <pre className={`${mono} whitespace-pre-wrap break-words text-slate-200`}>
          {lines.join('\n')}
        </pre>
      </div>
      <div className="px-4 py-2 text-[11px] opacity-60"
        style={{ borderTop: '1px solid var(--border)', color: 'var(--foreground)' }}>
        Live (refreshes every 2 s) · backend in-process + uvicorn + vite dev output
      </div>
    </div>
  )
}
