'use client'

import React, { useState } from 'react'

export default function FileUploader() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files).filter(file => 
        isCodeFile(file.name)
      )
      setSelectedFiles(prev => [...prev, ...newFiles])
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    
    const files = Array.from(e.dataTransfer.files).filter(file => 
      isCodeFile(file.name)
    )
    
    if (files.length > 0) {
      setSelectedFiles(prev => [...prev, ...files])
    }
  }

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }

  const isCodeFile = (filename: string) => {
    const allowedExtensions = [
      'js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'h', 'hpp',
      'go', 'rs', 'rb', 'php', 'swift', 'kt', 'scala', 'cs', 'vue',
      'svelte', 'html', 'css', 'scss', 'sass', 'json', 'yaml', 'yml',
      'sql', 'md', 'txt', 'sh', 'bash'
    ]
    
    const ext = filename.split('.').pop()?.toLowerCase()
    return allowedExtensions.includes(ext || '')
  }

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase()
    
    switch (ext) {
      case 'js':
      case 'jsx':
      case 'ts':
      case 'tsx': return '💻'
      case 'py': return '🐍'
      case 'java': return '☕'
      case 'go': return '🐹'
      case 'rs': return '⚙️'
      case 'html': return '🌐'
      case 'css': return '🎨'
      case 'json': return '📋'
      case 'md': return '📝'
      default: return '📄'
    }
  }

  const getFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return (
    <div className="border-2 border-dashed rounded-xl p-6" style={{ borderColor: 'var(--input-border)' }}>
      <input
        type="file"
        id="file-upload"
        className="hidden"
        multiple
        accept=".js,.jsx,.ts,.tsx,.py,.java,.c,.cpp,.h,.hpp,.go,.rs,.rb,.php,.swift,.kt,.scala,.cs,.vue,.svelte,.html,.css,.scss,.sass,.json,.yaml,.yml,.sql,.md,.txt,.sh,.bash"
        onChange={handleFileUpload}
      />

      {!selectedFiles.length ? (
        <label
          htmlFor="file-upload"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="cursor-pointer flex flex-col items-center justify-center py-8 px-4 rounded-lg hover:bg-zinc-800 transition-all"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--input-border)', marginBottom: '12px' }}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>

          <span className="font-medium mb-1" style={{ color: 'var(--foreground)' }}>
            Drag & drop code files here
          </span>
          <span className="text-sm opacity-60" style={{ color: 'var(--foreground)' }}>
            or click to browse (up to 10 files, max 5MB each)
          </span>
        </label>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-medium" style={{ color: 'var(--foreground)' }}>
              {selectedFiles.length} file(s) uploaded
            </span>
            <button
              onClick={() => setSelectedFiles([])}
              className="text-sm hover:underline"
              style={{ color: 'var(--accent)' }}
            >
              Clear all
            </button>
          </div>

          <div className="max-h-48 overflow-y-auto space-y-2 pr-2">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 rounded-lg"
                style={{ backgroundColor: 'var(--input-bg)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <span className="text-xl">{getFileIcon(file.name)}</span>
                  <div className="min-w-0">
                    <div className="font-medium truncate" style={{ color: 'var(--foreground)' }}>
                      {file.name}
                    </div>
                    <div className="text-xs opacity-50" style={{ color: 'var(--foreground)' }}>
                      {getFileSize(file.size)}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => removeFile(index)}
                  className="p-1 rounded hover:bg-red-500/20 transition-colors"
                  aria-label={`Remove ${file.name}`}
                  title="Remove file"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--foreground)', opacity: 0.5 }}>
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            ))}
          </div>

          {selectedFiles.length < 10 && (
            <label
              htmlFor="file-upload"
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className="cursor-pointer block text-center py-2 px-3 rounded border-2 border-dashed hover:bg-zinc-800/50 transition-all"
              style={{ borderColor: 'var(--accent)' }}
            >
              <span style={{ color: 'var(--accent)', fontSize: '14px' }}>
                + Add more files
              </span>
            </label>
          )}
        </div>
      )}
    </div>
  )
}
