"use client";

import { useEffect, useState } from 'react';

interface Props {
  apiUrl: string;
  model: string;
  setModel: (model: string) => void;
  availableModels: string[];
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  onClose: () => void;
}

interface OllamaStatus {
  up: boolean;
  model_count: number;
  models: string[];
  base_url: string;
  error?: string;
}

export default function SettingsPanel({
  apiUrl,
  model,
  setModel,
  availableModels,
  theme,
  toggleTheme,
  onClose,
}: Props) {
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [temperature, setTemperature] = useState(0.7);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [statusMsg, setStatusMsg] = useState('');

  const dark = theme === 'dark';
  const fieldCls = `w-full p-2 rounded border ${
    dark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-gray-300 text-gray-800'
  }`;

  // Load persisted settings + live Ollama status on mount.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiUrl}/api/settings`);
        const d = await res.json();
        setTemperature(d.temperature);
        setSystemPrompt(d.system_prompt || '');
      } catch {
        /* defaults stay */
      }
    })();
    fetchStatus();
  }, [apiUrl]);

  async function fetchStatus() {
    try {
      const res = await fetch(`${apiUrl}/api/ollama/status`);
      setStatus((await res.json()) as OllamaStatus);
    } catch {
      setStatus({ up: false, model_count: 0, models: [], base_url: '', error: 'backend unreachable' });
    }
  }

  async function save(partial: { temperature?: number; system_prompt?: string }) {
    try {
      const res = await fetch(`${apiUrl}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(partial),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStatusMsg('Saved');
    } catch {
      setStatusMsg('Save failed — is the backend up?');
    }
    window.setTimeout(() => setStatusMsg(''), 2000);
  }

  const inputCls = `flex-1 rounded px-2 py-1 text-xs ${
    dark ? 'bg-slate-800 text-slate-300 border border-slate-700' : 'bg-gray-100 text-gray-600 border border-gray-300'
  }`;

  return (
    <div className="flex flex-col h-full p-4 space-y-5 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Settings</h2>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-slate-700"
          aria-label="Close settings"
        >
          ✖️
        </button>
      </div>

      {/* Ollama status (read-only) */}
      <div>
        <label className={`block mb-1 text-sm font-medium ${dark ? 'text-slate-300' : 'text-gray-600'}`}>
          Ollama
        </label>
        {status === null ? (
          <div className={`text-xs ${dark ? 'text-slate-500' : 'text-gray-400'}`}>Checking…</div>
        ) : (
          <div className={`rounded border p-2 text-xs space-y-1 ${
            status.up
              ? dark ? 'border-emerald-800 bg-emerald-900/30 text-emerald-300' : 'border-emerald-300 bg-emerald-50 text-emerald-700'
              : dark ? 'border-red-800 bg-red-900/30 text-red-300' : 'border-red-300 bg-red-50 text-red-700'
          }`}>
            <div className="font-medium">{status.up ? `● Up — ${status.model_count} model(s) installed` : '● Down'}</div>
            <div>Endpoint: {status.base_url || 'unknown'}</div>
            {!status.up && status.error && <div className="opacity-80 truncate">{status.error}</div>}
            {status.up && status.models.length > 0 && (
              <div className="opacity-80 truncate" title={status.models.join(', ')}>
                {status.models.join(', ')}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Default model picker (persisted for the session; falls back to first available) */}
      <div>
        <label className={`block mb-1 text-sm font-medium ${dark ? 'text-slate-300' : 'text-gray-600'}`}>
          Model
        </label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className={fieldCls}
        >
          {availableModels.length > 0 ? (
            availableModels.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))
          ) : (
            <option value={model}>{model}</option>
          )}
        </select>
      </div>

      {/* Temperature slider — persisted in the SQLite settings store */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-sm font-medium" htmlFor="temperature-slider">
            Temperature
          </label>
          <input
            id="temperature-slider-value"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={temperature}
            onChange={(e) => {
              const v = Math.min(1, Math.max(0, Number(e.target.value) || 0));
              setTemperature(v);
              save({ temperature: v });
            }}
            className={inputCls}
            aria-label="Temperature value"
          />
        </div>
        <input
          id="temperature-slider"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={temperature}
          onChange={(e) => {
            const v = Number(e.target.value);
            setTemperature(v);
            save({ temperature: v });
          }}
          className="w-full"
          aria-label="Temperature"
        />
        <div className={`text-xs ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
          0 = deterministic · 1 = creative (applies to new chats)
        </div>
      </div>

      {/* System prompt — persisted in SQLite */}
      <div>
        <label className={`block mb-1 text-sm font-medium ${dark ? 'text-slate-300' : 'text-gray-600'}`}>
          System prompt
        </label>
        <textarea
          rows={4}
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          onBlur={() => save({ system_prompt: systemPrompt })}
          placeholder="How should the assistant behave? (e.g. tone, formatting, what to cite)"
          className={fieldCls}
        />
        <div className={`text-xs ${dark ? 'text-slate-500' : 'text-gray-400'}`}>
          Saved when you leave the field. Applies to new chats only.
        </div>
      </div>

      {/* OpenRouter — coming in v1.1 (don't ship a dead control) */}
      <div className="opacity-60">
        <div className="flex items-center justify-between">
          <label className={`block text-sm font-medium ${dark ? 'text-slate-400' : 'text-gray-500'}`}>
            OpenRouter (cloud)
          </label>
          <span className={`text-xs rounded px-2 py-1 ${dark ? 'bg-slate-800 text-slate-400' : 'bg-gray-100 text-gray-500'}`}>
            coming in v1.1
          </span>
        </div>
        <input
          type="text"
          placeholder="API key (v1.1)"
          disabled
          className={`${fieldCls} mt-1`}
          aria-label="OpenRouter API key (coming in v1.1)"
        />
      </div>

      {/* Theme + save feedback */}
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium">Theme</label>
        <button onClick={toggleTheme} className="flex-1 p-2 rounded bg-indigo-600 text-white">
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>

      {statusMsg && (
        <div className={`text-xs text-center ${dark ? 'text-indigo-300' : 'text-indigo-600'}`}>{statusMsg}</div>
      )}
    </div>
  );
}
