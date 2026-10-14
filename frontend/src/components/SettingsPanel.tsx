"use client";

import { useState } from 'react';

interface Props {
  model: string;
  setModel: (model: string) => void;
  availableModels: string[];
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  onClose: () => void;
}

export default function SettingsPanel({
  model,
  setModel,
  availableModels,
  theme,
  toggleTheme,
  onClose,
}: Props) {
  return (
    <div className="flex flex-col h-full p-4 space-y-4">
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

      <div>
        <label className="block mb-1 text-sm font-medium">Model</label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className={`w-full p-2 rounded border ${theme === 'dark' ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-gray-300 text-gray-800'} `}
        >
          {availableModels.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2">
        <label className="text-sm font-medium">Theme</label>
        <button onClick={toggleTheme} className="flex-1 p-2 rounded bg-indigo-600 text-white">
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </div>
    </div>
  );
}
