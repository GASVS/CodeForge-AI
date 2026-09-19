'use client'

import { useState, useCallback } from 'react'
import { Send } from 'lucide-react'

interface Props {
  onSend: (content: string) => void
  disabled: boolean
}

export default function MessageInput({ onSend, disabled }: Props) {
  const [input, setInput] = useState('')

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || disabled) return
    
    onSend(input)
    setInput('')
  }, [input, disabled, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div 
      className="border-t p-4" 
      style={{ backgroundColor: 'var(--sidebar-bg)', borderColor: 'var(--border)' }}
    >
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
        <div 
          className="flex items-end gap-3 rounded-xl border overflow-hidden focus-within:border-blue-500 transition-colors"
          style={{ backgroundColor: 'var(--input-bg)', borderColor: 'var(--input-border)' }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message... (Shift+Enter for new line)"
            disabled={disabled}
            className="flex-1 bg-transparent px-4 py-3 resize-none max-h-32 min-h-[52px] outline-none transition-colors"
            style={{ color: 'var(--foreground)' }}
            rows={1}
            style={{ height: 'auto', minHeight: '52px' }}
          />
          
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            className="m-2 p-2 rounded-lg transition-colors flex-shrink-0"
            style={{ 
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
              opacity: !input.trim() || disabled ? 0.5 : 1,
              cursor: !input.trim() || disabled ? 'not-allowed' : 'pointer'
            }}
            aria-label="Send message"
          >
            <Send size={18} />
          </button>
        </div>
        
        <div 
          className="text-center text-xs mt-2" 
          style={{ color: 'var(--foreground)', opacity: 0.5 }}
        >
          Powered by local LLM • Your code stays private
        </div>
      </form>
    </div>
  )
}
