import { useEffect, useState } from 'react'
import { Chat } from '@/types/chat'

interface ChatSidebarProps {
  apiUrl: string
  selectedId: string | null
  onSelect: (id: string) => void
  onCreate?: (title: string) => void
  onDelete?: (id: string) => void
}

export default function ChatSidebar({ apiUrl, selectedId, onSelect, onCreate, onDelete }: ChatSidebarProps) {
  const [chatList, setChatList] = useState<Chat[]>([])
  const fetchChats = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/chats`)
      const data = await res.json()
      setChatList(data.chats)
    } catch (e) {
      console.error('Failed to load chats', e)
    }
  }
  useEffect(() => { fetchChats() }, [])

  const handleCreate = async () => {
    const title = prompt('New chat title')
    if (!title) return
    try {
      const res = await fetch(`${apiUrl}/api/chats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      })
      const newChat = await res.json()
      setChatList([...chatList, newChat])
      if (onCreate) onCreate(newChat.id)
    } catch (e) {
      console.error('Create error', e)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete chat?')) return
    try {
      await fetch(`${apiUrl}/api/chats/${id}`, { method: 'DELETE' })
      setChatList(chatList.filter(c => c.id !== id))
      if (onDelete) onDelete(id)
    } catch (e) {
      console.error('Delete error', e)
    }
  }

  return (
    <div className="w-80 bg-sidebar border-r">
      <div className="p-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Chats</h2>
        <button onClick={handleCreate} className="text-sm underline">+ New</button>
      </div>
      <ul>
        {chatList.map(c => (
          <li key={c.id} className={`px-4 py-2 hover:bg-muted cursor-pointer ${c.id === selectedId ? 'bg-muted' : ''}`}>
            <div onClick={() => onSelect(c.id)} className="flex items-center gap-2">
              {'parent_chat_id' in c && c.parent_chat_id ? (
                <span className="text-xs opacity-50" title={`Branched from ${c.parent_chat_id}`}>⑂</span>
              ) : (
                <span className="text-xs opacity-30">•</span>
              )}
              <span className="flex-1 truncate">{c.title || 'Untitled'}</span>
            </div>
            <button onClick={() => handleDelete(c.id)} className="text-sm text-red-500">x</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
