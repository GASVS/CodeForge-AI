'use client'

import { useState, useEffect, useRef } from 'react'
import MessageList from '@/components/MessageList'
import MessageInput from '@/components/MessageInput'
import SettingsPanel from '@/components/SettingsPanel'
import FileUploader from '@/components/FileUploader'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
}

const STORAGE_KEYS = {
  THEME: 'jev-theme',
  MODEL: 'jev-model'
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      content: 'Hello! I\'m your AI coding assistant. I can help you write code, explain concepts, debug issues, and more. What would you like to work on today?',
      role: 'assistant',
      timestamp: new Date()
    }
  ])
  const [model, setModel] = useState('qwen3.5-9b-64k:latest')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [showSettings, setShowSettings] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

  // Load theme from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'dark' | 'light' | null
    if (savedTheme) {
      setTheme(savedTheme)
      document.documentElement.setAttribute('data-theme', savedTheme)
    }
  }, [])

  // Toggle theme mode
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  // Fetch available models on mount
  useEffect(() => {
    fetchModels()
  }, [])

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const fetchModels = async () => {
    try {
      const res = await fetch(`${API_URL}/api/models`)
      const data = await res.json()
      setAvailableModels(data.models || [])
    } catch (err) {
      console.error('Failed to fetch models:', err)
    }
  }

  const sendMessage = async (content: string) => {
    if (!content.trim()) return

    const userMsg: Message = {
      id: Date.now().toString(),
      content,
      role: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    // Prepare assistant message placeholder
    const assistantMsgId = (Date.now() + 1).toString()
    const assistantMsg: Message = {
      id: assistantMsgId,
      content: '',
      role: 'assistant',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, assistantMsg])

    try {
      // Use EventSource for SSE streaming
      const eventSource = new EventSource(`${API_URL}/stream/api/chat?message=${encodeURIComponent(content)}&model_name=${encodeURIComponent(model)}`)
      
      let fullContent = ''
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.text) {
            fullContent += data.text
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMsgId ? { ...msg, content: fullContent } : msg
              )
            )
          }
        } catch (e) {
          console.error('Failed to parse stream data:', e)
        }
      }

      eventSource.onerror = (error) => {
        console.error('EventSource failed:', error)
        eventSource.close()
        setIsLoading(false)
      }

      // Wait for stream completion (manual timeout as fallback)
      const timeout = setTimeout(() => {
        eventSource.close()
        setIsLoading(false)
      }, 60000) // 60s max timeout

      // Listen for completion marker
      eventSource.addEventListener('end', () => {
        clearTimeout(timeout)
        eventSource.close()
        setIsLoading(false)
      })

    } catch (err) {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, content: 'Error: Could not connect to AI service. Is Ollama running?' }
            : msg
        )
      )
      console.error('Chat error:', err)
      setIsLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full w-80 bg-sidebar border-r transition-all duration-300 ${
          showSettings ? 'translate-x-0' : '-translate-x-full'
        } z-50`}
        style={{ backgroundColor: 'var(--sidebar-bg)', borderColor: 'var(--border)' }}
      >
        <SettingsPanel
          model={model}
          setModel={setModel}
          availableModels={availableModels}
          theme={theme}
          toggleTheme={toggleTheme}
          onClose={() => setShowSettings(false)}
        />
      </aside>

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col ml-0 transition-all duration-200">
        {/* Header */}
        <header 
          className="border-b px-6 py-4"
          style={{ backgroundColor: 'var(--sidebar-bg)', borderColor: 'var(--border)' }}
        >
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowSettings(true)}
              className="text-zinc-400 hover:text-white transition-colors"
              aria-label="Settings"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
              </svg>
            </button>

            <h1 className="text-xl font-semibold">Jev Open Source</h1>

            <div className="flex items-center gap-4">
              <span style={{ color: 'var(--foreground)', opacity: 0.5 }} className="text-sm font-mono">
                {model.split(':')[0]}
              </span>
              
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg transition-all"
                style={{ backgroundColor: 'var(--muted)', color: 'var(--foreground)' }}
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                {theme === 'dark' ? (
                  // Sun icon for light mode
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
                ) : (
                  // Moon icon for dark mode
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                  </svg>
                )}
              </button>
            </div>
          </div>
        </header>

        {/* Messages */}
        <MessageList messages={messages} isLoading={isLoading} />
        <div ref={messagesEndRef} />

        {/* File Uploader Panel */}
        {uploadedFiles.length > 0 && (
          <div 
            className="border-t p-4"
            style={{ borderColor: 'var(--border)', backgroundColor: 'var(--muted)' }}
          >
            <FileUploader 
              onFileSelect={(files) => setUploadedFiles(prev => [...prev, ...files])}
              uploadedCount={uploadedFiles.length}
            />
          </div>
        )}

        {/* Input Area */}
        <MessageInput onSend={sendMessage} disabled={isLoading} />
      </main>

      {/* Settings Overlay */}
      {showSettings && (
        <div
          className="fixed inset-0 bg-black/50 z-40"
          onClick={() => setShowSettings(false)}
        />
      )}
    </div>
  )
}
