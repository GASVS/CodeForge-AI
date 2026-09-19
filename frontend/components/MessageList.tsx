'use client'

import React from 'react'

interface Props {
  messages: Array<{ id: string; content: string; role: 'user' | 'assistant'; timestamp: Date }>
  isLoading: boolean
}

export default function MessageList({ messages, isLoading }: Props) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6" style={{ background: 'var(--background)' }}>
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${
            msg.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className="max-w-[80%] rounded-2xl px-5 py-3 shadow-sm"
            style={{ 
              background: msg.role === 'user' ? 'var(--message-user)' : 'var(--message-ai)',
              color: msg.role === 'user' ? 'var(--message-user-text)' : 'var(--message-ai-text)',
              transition: 'background-color 0.2s ease, color 0.2s ease'
            }}
          >
            <div className="whitespace-pre-wrap break-words">{msg.content}</div>
            <div className="text-xs mt-2 opacity-60" style={{ color: 'inherit' }}>
              {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        </div>
      ))}

      {isLoading && (
        <div className="flex justify-start">
          <div className="rounded-2xl px-5 py-4 shadow-sm" style={{ background: 'var(--message-ai)' }}>
            <div className="flex space-x-2">
              <div className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--foreground)', opacity: 0.5 }} />
              <div className="w-2 h-2 rounded-full animate-bounce delay-75" style={{ backgroundColor: 'var(--foreground)', opacity: 0.5 }} />
              <div className="w-2 h-2 rounded-full animate-bounce delay-150" style={{ backgroundColor: 'var(--foreground)', opacity: 0.5 }} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
