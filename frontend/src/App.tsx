'use client'

import { useState, useEffect, useRef } from 'react';
import MessageList from './components/MessageList';
import MessageInput from './components/MessageInput';
import SettingsPanel from './components/SettingsPanel';
import FileContext from './FileContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface UploadedFile {
  id: string;
  filename: string;
  size: number | string;
}
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
}

function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 6L6 18M6 6l12 12"/>
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="12" x2="21" y2="12"/>
      <line x1="3" y1="6" x2="21" y2="6"/>
      <line x1="3" y1="18" x2="21" y2="18"/>
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/>
      <line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  );
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      content: "Hello! I'm your AI coding assistant. I can help you write code, explain concepts, debug issues, and more. Running locally with Ollama — your data stays private. What would you like to work on today?",
      role: 'assistant',
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [model, setModel] = useState('qwen3.5-9b-64k:latest');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

  // Load theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('jev-theme') as 'dark' | 'light' | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }, []);

  // Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await fetch(`${API_URL}/api/models`);
        const data = await res.json();
        setAvailableModels(data.models || []);
      } catch (err) {
        console.error('Failed to fetch models:', err);
      }
    };
    fetchModels();
  }, [API_URL]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('jev-theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantMsgId,
      content: '',
      role: 'assistant',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, assistantMsg]);

    try {
      // Use SSE streaming for real-time updates
      const eventSource = new EventSource(
        `${API_URL}/stream/api/chat?message=${encodeURIComponent(content)}&model_name=${encodeURIComponent(model)}`
      );

      let fullContent = '';

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.text) {
            fullContent += data.text;
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMsgId ? { ...msg, content: fullContent } : msg
              )
            );
          } else if (data.error) {
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMsgId ? { ...msg, content: `Error: ${data.error}` } : msg
              )
            );
          }
        } catch (e) {
          console.error('Failed to parse stream data:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource failed:', error);
        eventSource.close();
        setIsLoading(false);
      };

      // Timeout fallback
      setTimeout(() => {
        eventSource.close();
        setIsLoading(false);
      }, 120000);
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId
            ? { ...msg, content: '❌ Error: Cannot connect to backend. Make sure it\'s running on http://localhost:8001' }
            : msg
        )
      );
      setIsLoading(false);
    }
  };

  const clearChat = () => setMessages([{
    id: Date.now().toString(),
    content: "Chat cleared! What would you like to work on?",
    role: 'assistant',
    timestamp: new Date()
  }]);

  const suggestions = [
    'Explain how async/await works in JavaScript',
    'Write a Python function to parse JSON files',
    'What is the difference between map and filter?',
    'Generate a React component for a login form',
  ];

  // Theme-aware styles
  const containerBg = theme === 'dark' ? 'bg-slate-950' : 'bg-gray-50';
  const textColor = theme === 'dark' ? 'text-slate-100' : 'text-gray-900';
  const headerBg = theme === 'dark' ? 'bg-slate-950/95' : 'bg-white';
  const borderColor = theme === 'dark' ? 'border-slate-800' : 'border-gray-200';

  return (
    <div className={`min-h-screen ${containerBg} ${textColor}`}>
      {/* Settings Sidebar */}
      {showSettings && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setShowSettings(false)}
          />
          <aside className="fixed left-0 top-0 h-full w-96 bg-slate-900 border-r border-slate-700 z-50 shadow-xl">
            <SettingsPanel
              model={model}
              setModel={(m: string) => { setModel(m); setShowSettings(false); }}
              availableModels={availableModels}
              theme={theme}
              toggleTheme={toggleTheme}
              onClose={() => setShowSettings(false)}
            />
          </aside>
        </>
      )}

      {/* Header */}
      <header className={`border-b ${borderColor} p-4 sticky top-0 ${headerBg} backdrop-blur z-10`}>
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
              title="Settings"
            >
              <SettingsIcon />
            </button>
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Jev Open Source Dashboard
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {/* Model Selector */}
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className={`bg-slate-900 border ${borderColor} rounded-lg px-3 py-2 text-sm hover:border-indigo-500 transition-colors`}
            >
              {availableModels.length > 0 ? (
                availableModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))
              ) : (
                <>
                  <option value="qwen3.5-9b-64k:latest">Qwen 3.5 9B</option>
                  <option value="qwen3.5-27b-64k:latest">Qwen 3.5 27B</option>
                </>
              )}
            </select>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            </button>

            {/* Clear Chat */}
            <button
              onClick={clearChat}
              className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
              title="Clear chat"
            >
              <XIcon />
            </button>
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <main className="max-w-6xl mx-auto p-4 pb-32">
        {messages.length === 1 && messages[0].id === 'welcome' ? (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400">
            <div className="mb-6">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-indigo-500">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
              </svg>
            </div>
            <h2 className="text-2xl font-semibold text-slate-200 mb-2">Welcome to your AI assistant</h2>
            <p className="text-center max-w-md mb-8">
              Ask me anything about code, explain concepts, generate functions, or chat freely.
              Running locally with Ollama — 100% private.
            </p>

            <div className="grid grid-cols-2 gap-3 max-w-lg w-full">
              {suggestions.map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => setInput(suggestion)}
                  className={`p-4 ${theme === 'dark' ? 'bg-slate-900 border-slate-800 hover:border-indigo-500' : 'bg-white border-gray-200 hover:border-indigo-500'} rounded-lg transition-colors text-left text-sm`}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2 mb-4">
            {messages.map((msg, i) => {
              const isAssistant = msg.role === 'assistant';
              return (
                <div
                  key={msg.id}
                  className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[80%] p-4 rounded-2xl ${
                      isAssistant
                        ? `${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'} border`
                        : 'bg-indigo-600 text-white'
                    }`}
                  >
                    {isAssistant ? (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            code({ node, inline, className, children, ...props }: any) {
                              const match = /language-(\w+)/.exec(className || '');
                              const language = match ? match[1] : 'text';
                              const codeText = String(children).replace(/\n$/, '');
                              
                              if (!inline && match) {
                                return (
                                  <div className="relative my-3 rounded-lg overflow-hidden">
                                    <pre className={`p-4 ${theme === 'dark' ? 'bg-slate-950' : 'bg-gray-100'} overflow-x-auto`}>
                                      <code className={className} {...props}>
                                        {children}
                                      </code>
                                    </pre>
                                    <button
                                      onClick={() => navigator.clipboard.writeText(codeText)}
                                      className="absolute top-2 right-2 p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white transition-colors"
                                      title="Copy code"
                                    >
                                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                                      </svg>
                                    </button>
                                  </div>
                                );
                              }
                              return (
                                <code className="px-1 py-0.5 rounded bg-slate-700/50 text-sm" {...props}>
                                  {children}
                                </code>
                              );
                            }
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    )}
                    <div className={`text-xs mt-2 ${isAssistant ? 'opacity-50' : 'opacity-75'}`}>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              );
            })}

            {isLoading && (
              <div className="flex justify-start">
                <div className={`${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'} border p-4 rounded-2xl`}>
                  <div className="flex gap-2 items-center">
                    <span className="animate-spin">⟳</span>
                    <span className="opacity-60">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* File Upload Info (when files uploaded) */}
      {uploadedFiles.length > 0 && (
        <div className={`fixed left-4 right-4 bottom-[180px] max-w-6xl mx-auto ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'} border rounded-xl p-3 shadow-lg z-20`}>
          <div className="flex items-center justify-between">
            <span className="text-sm">📎 {uploadedFiles.length} file(s) attached</span>
            <button
              onClick={() => setUploadedFiles([])}
              className="text-xs opacity-60 hover:opacity-100"
            >
              Clear all
            </button>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className={`fixed bottom-0 left-0 right-0 border-t ${borderColor} ${headerBg} p-4`}>
        <div className="max-w-6xl mx-auto flex gap-3">
          {/* File Upload Button */}
          <label className="cursor-pointer p-3 hover:bg-slate-800 rounded-xl transition-colors" title="Upload files">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="opacity-60 hover:opacity-100">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <input
              type="file"
              className="hidden"
              multiple
              accept=".js,.jsx,.ts,.tsx,.py,.java,.c,.cpp,.go,.rs,.html,.css,.json,.md,.txt,.sh"
              onChange={(e) => {
                if (e.target.files) {
                  setUploadedFiles(prev => [...prev, ...Array.from(e.target.files)]);
                }
              }}
            />
          </label>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !isLoading && sendMessage(input)}
            placeholder="Type your message..."
            disabled={isLoading}
            className={`flex-1 ${theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-gray-50 border-gray-200'} border rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 transition-colors`}
          />

          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
            className="p-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-800 disabled:cursor-not-allowed rounded-xl transition-colors flex items-center justify-center min-w-[48px]"
          >
            <SendIcon />
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
