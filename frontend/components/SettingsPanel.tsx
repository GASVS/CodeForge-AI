'use client'

import React, { useState } from 'react'

interface Props {
  model: string
  setModel: (model: string) => void
  availableModels: string[]
  theme: 'dark' | 'light'
  toggleTheme: () => void
  onClose: () => void
}

export default function SettingsPanel({ 
  model, 
  setModel, 
  availableModels, 
  theme, 
  toggleTheme,
  onClose 
}: Props) {
  const [localModel, setLocalModel] = useState(model)

  const handleSave = () => {
    setModel(localModel)
    onClose()
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-zinc-700 bg-[#18181b]">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-white">
            ✕
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        {/* Theme Toggle */}
        <section
          className="p-4 rounded-xl"
          style={{ backgroundColor: 'var(--input-bg)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center justify-between">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--foreground)' }}>
                Appearance
              </label>
              <p className="text-xs opacity-60" style={{ color: 'var(--foreground)' }}>
                {theme === 'dark' ? 'Dark mode (default)' : 'Light mode'}
              </p>
            </div>
            
            <button
              onClick={toggleTheme}
              className="px-4 py-2 rounded-lg font-medium transition-all"
              style={{ 
                backgroundColor: 'var(--accent)', 
                color: theme === 'dark' ? '#ffffff' : '#18181b' 
              }}
            >
              {theme === 'dark' ? (
                <span className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="5"></circle>
                    <line x1="12" y1="1" x2="12" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="23"></line>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                    <line x1="1" y1="12" x2="3" y2="12"></line>
                    <line x1="21" y1="12" x2="23" y2="12"></line>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                  </svg>
                  Switch to Light
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                  </svg>
                  Switch to Dark
                </span>
              )}
            </button>
          </div>
        </section>

        {/* Model Selection */}
        <section>
          <label className="block text-sm font-medium text-zinc-300 mb-2">
            AI Model
          </label>
          <select
            value={localModel}
            onChange={(e) => setLocalModel(e.target.value)}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            {availableModels.length > 0 ? (
              availableModels.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))
            ) : (
              <option>No models available</option>
            )}
          </select>
          
          <p className="text-xs text-zinc-500 mt-2">
            Model running locally via Ollama
          </p>
        </section>

        {/* API Settings (future) */}
        <section>
          <h3 className="text-sm font-medium text-zinc-300 mb-3">API Configuration</h3>
          
          <label className="block text-xs text-zinc-400 mb-1">
            Backend URL
          </label>
          <input
            type="text"
            value="http://localhost:8001"
            disabled
            className="w-full px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-500 text-sm cursor-not-allowed"
          />

          <p className="text-xs text-zinc-500 mt-2 mb-4">
            Edit directly in code for now
          </p>
        </section>

        {/* About */}
        <section>
          <h3 className="text-sm font-medium text-zinc-300 mb-3">About</h3>
          <div className="space-y-2 text-sm text-zinc-400">
            <p><strong className="text-white">Version:</strong> 0.1.0 (Alpha)</p>
            <p><strong className="text-white">License:</strong> MIT Open Source</p>
            <p><strong className="text-white">Privacy:</strong> All processing is local</p>
          </div>

          <a
            href="https://github.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-4 text-blue-400 hover:text-blue-300 text-sm"
          >
            View on GitHub →
          </a>
        </section>
      </div>

      {/* Footer */}
      <div className="p-6 border-t border-zinc-700 bg-[#18181b]">
        <button
          onClick={handleSave}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
        >
          Save Changes
        </button>
      </div>
    </div>
  )
}
