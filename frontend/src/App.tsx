'use client'

import { useState, useEffect, useRef } from 'react';
import SettingsPanel from '../components/SettingsPanel';
import ChatSidebar from '../components/ChatSidebar';
import LogsPanel from '../components/LogsPanel';
import FileContext from './FileContext';
import ProjectPanel from './ProjectPanel';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import css from 'react-syntax-highlighter/dist/esm/languages/prism/css';
import jsx from 'react-syntax-highlighter/dist/esm/languages/prism/jsx';
import oneDark from 'react-syntax-highlighter/dist/esm/styles/prism/one-dark';
import oneLight from 'react-syntax-highlighter/dist/esm/styles/prism/one-light';

SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('typescript', typescript);
SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('jsx', jsx);

interface UploadedFile {
  id: string;
  filename: string;
  size: number;
}

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  error?: string; // Phase 4: styled error card instead of inline text
  toolCalls?: Array<{ id: string; name: string; args: any }>;
  toolResults?: Record<string, any>;
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
  const [streamStarted, setStreamStarted] = useState(false);
  const [model, setModel] = useState('qwen3.5-9b-64k:latest');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  // Phase 4.2 empty states: null = haven't reached the backend yet,
  // true = Ollama/models reachable, false = Ollama (or backend) offline.
  // Drives the "Ollama offline" card on the empty state.
  const [ollamaUp, setOllamaUp] = useState<boolean | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  // Which bottom panel the 📎 button opens: null (closed) | 'files' | 'projects'.
  // The button cycles: files → projects → closed → files…
  const [contextTab, setContextTab] = useState<null | 'files' | 'projects'>(null);
  // Live set of the current project's file IDs (kept from the last panel load so
  // we can drop stale selections when a project is replaced/deleted).
  const lastProjectFileIds = useRef<Set<string>>(new Set());
  // Keyboard (Phase 4.2): a Ctrl/Cmd+K pressed while NO panel is open should
  // open the projects panel and THEN focus its search box — focus happens in
  // this effect after the panel has committed to the DOM.
  const searchFocusArmed = useRef(false);
  // P3.2 RAG mode: when set, chat sends `project_ids=<id>` instead of the
  // selected-file concat — the backend picks the top relevant chunks for the
  // question. Toggled from ProjectPanel; cleared when the active project is
  // replaced/deleted so a stale id never reaches the stream endpoint.
  const [ragProjectId, setRagProjectId] = useState<string | null>(null);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<any[]>([]);
  const [showSidebar, setShowSidebar] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Live reference to the active SSE stream so the Stop button can abort it
  const streamRef = useRef<{ es: EventSource; close: (reason?: 'done' | 'stop' | 'timeout') => void } | null>(null);
  // Ref so the "Refactor" code action can prefill + focus the input box.
  // Phase 4.2: the box is now a (1-line) auto-growing textarea so
  // Shift+Enter inserts a real newline — Enter alone still sends.
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // P7.2 patch apply UI state
  const [patchApplyingId, setPatchApplyingId] = useState<string | null>(null);
  const [patchFeedback, setPatchFeedback] = useState<Record<string, { ok: boolean; message: string }>>({});
  // P7.3 structured findings selection state (per message id → selected finding indices)
  const [findingsSelection, setFindingsSelection] = useState<Record<string, number[]>>({});
  // P7.5 token usage from the last completed stream
  const [lastUsage, setLastUsage] = useState<{ prompt_tokens: number; completion_tokens: number; total_tokens: number } | null>(null);
  // P7.6 context compression notice from the stream
  const [compressedNote, setCompressedNote] = useState<string | null>(null);
  // P7.8 prompt templates (skills)
  const [skills, setSkills] = useState<{ name: string; title: string; body: string; model_override?: string }[]>([]);
  const [showSkillPalette, setShowSkillPalette] = useState(false);

  const loadSkills = () =>
    fetch(`${API_URL}/api/skills`)
      .then(r => r.ok ? r.json() : { skills: [] })
      .then(d => setSkills(d.skills || []))
      .catch(() => setSkills([]));

  const insertSkill = (body: string) => {
    setInput(prev => (prev ? prev + '\n\n' : '') + body);
    setShowSkillPalette(false);
    inputRef.current?.focus();
  };

  // P7.9 multimodal input: pending image URLs attached to the next message
  const [pendingImages, setPendingImages] = useState<string[]>([]);

  const uploadImages = async (files: FileList | File[]) => {
    const list = Array.from(files);
    const allowed = list.filter(f => {
      const ext = f.name.split('.').pop()?.toLowerCase() || '';
      return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext);
    });
    if (allowed.length === 0) return;
    const fd = new FormData();
    allowed.forEach(f => fd.append('files', f));
    try {
      const res = await fetch(`${API_URL}/api/upload`, { method: 'POST', body: fd });
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      const urls = (data.files || [])
        .filter((f: any) => f.url)
        .map((f: any) => f.url);
      setPendingImages(prev => [...prev, ...urls]);
    } catch (e) {
      console.error('Image upload failed:', e);
    }
  };

  const removePendingImage = (url: string) => {
    setPendingImages(prev => prev.filter(u => u !== url));
  };

  const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8001';

  useEffect(() => {
    loadSkills();
  }, [API_URL]);

  // Load theme from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('jev-theme') as 'dark' | 'light' | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  }, []);

  // Fetch available models; also records Ollama reachability for the
  // empty-state "offline" card. Exposed (not just called from the effect)
  // so the card's "Check again" button can re-probe without a remount.
  const fetchModels = () =>
    fetch(`${API_URL}/api/models`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        const models: string[] = (data && data.models) || [];
        setAvailableModels(models);
        setOllamaUp(true);
        // Fall back to the first locally available model if the default isn't installed
        setModel((current) =>
          models.length > 0 && !models.includes(current) ? models[0] : current
        );
      })
      .catch(err => {
        console.error('Failed to fetch models:', err);
        setAvailableModels([]);
        setOllamaUp(false);
      });

  useEffect(() => {
    fetchModels();
    // Keep the empty state honest while it's on screen: re-probe every 10 s
    // so "check again" is also automatic once Ollama comes back.
    const t = setInterval(fetchModels, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [API_URL]);

  const loadChatList = () =>
    fetch(`${API_URL}/api/chats`).then(r => r.json()).then(d => setChats(d.chats || [])).catch(() => {});

  const newChatState = () => ({
    id: (Date.now() + Math.random()).toString(),
    content: "Chat cleared! What would you like to work on?",
    role: 'assistant' as const,
    timestamp: new Date(),
  });

  const persistChat = async (chatId: string, msgs: Message[]) => {
    try {
      await fetch(`${API_URL}/api/chats/${chatId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: msgs.map(m => ({ role: m.role, content: m.content })),
        }),
      });
      loadChatList();
    } catch (e) {
      console.error('Failed to save chat:', e);
    }
  };

  const handleSelectChat = async (id: string) => {
    // Picking a chat closes the popup so the conversation is fully visible
    setShowSidebar(false);
    if (id === currentChatId) return;
    try {
      const res = await fetch(`${API_URL}/api/chats/${id}`);
      if (!res.ok) throw new Error(res.statusText);
      const chat = await res.json();
      setCurrentChatId(id);
      setMessages(
        (chat.messages || []).map((m: any, i: number) => ({
          id: `${id}-${i}`,
          content: m.content || '',
          role: m.role === 'user' ? ('user' as const) : ('assistant' as const),
          timestamp: new Date(),
        }))
      );
    } catch (e) {
      console.error('Failed to open chat:', e);
    }
  };

  const handleCreateChat = (id: string) => {
    setCurrentChatId(id);
    setMessages([newChatState()]);
    setShowSidebar(false);
  };

  const handleDeleteChat = (id: string) => {
    if (id === currentChatId) {
      setCurrentChatId(null);
      setMessages([newChatState()]);
    }
    loadChatList();
  };

  const handleExportChat = async (format: 'md' | 'json' = 'md') => {
    if (!currentChatId) return;
    const res = await fetch(`${API_URL}/api/chats/${currentChatId}/export?format=${format}`);
    if (!res.ok) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(await res.blob());
    a.download = `${currentChatId}.${format === 'md' ? 'md' : 'json'}`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  // Load saved chats on mount; restore the most recent conversation if one exists
  useEffect(() => {
    fetch(`${API_URL}/api/chats`)
      .then(r => r.json())
      .then(d => {
        const list = d.chats || [];
        setChats(list);
        if (list.length > 0) {
          setCurrentChatId(list[0].id);
          return fetch(`${API_URL}/api/chats/${list[0].id}`).then(r => r.json());
        }
        return Promise.resolve(null);
      })
      .then(chat => {
        if (chat && Array.isArray(chat.messages) && chat.messages.length > 0) {
          setMessages(
            chat.messages.map((m: any, i: number) => ({
              id: `${chat.id}-${i}`,
              content: m.content || '',
              role: m.role === 'user' ? 'user' : 'assistant',
              timestamp: new Date(),
            }))
          );
        }
      })
      .catch(err => console.error('Failed to load chat history:', err));
  }, [API_URL]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Phase 4.2 keyboard shortcuts ───────────────────────────────────
  // Esc  → close the topmost overlay (context panel → logs → settings → history)
  // ⌘/Ctrl+K → open the projects panel if needed, then focus its search box
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (contextTab !== null) setContextTab(null);
        else if (showLogs) setShowLogs(false);
        else if (showSettings) setShowSettings(false);
        else if (showSidebar) setShowSidebar(false);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        const focusSearch = () => {
          const el = document.querySelector<HTMLInputElement>('[data-codeforge-search]');
          el?.focus();
          el?.select();
        };
        if (contextTab === 'projects') {
          // already open → focus immediately
          focusSearch();
        } else {
          searchFocusArmed.current = true;
          setContextTab('projects');
        }
        return;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [contextTab, showLogs, showSettings, showSidebar]);

  // Second half of ⌘/Ctrl+K: the panel just mounted — focus its search box.
  useEffect(() => {
    if (!searchFocusArmed.current) return;
    searchFocusArmed.current = false;
    const t = setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>('[data-codeforge-search]');
      el?.focus();
      el?.select();
    }, 50);
    return () => clearTimeout(t);
  }, [contextTab]);


  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('jev-theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const retryLastMessage = () => {
    const userMsg = [...messages].reverse().find(m => m.role === 'user');
    const assistantMsg = messages[messages.length - 1];
    if (!userMsg || !assistantMsg || assistantMsg.role !== 'assistant') return;
    setMessages(prev => prev.filter(m => m.id !== userMsg.id && m.id !== assistantMsg.id));
    sendMessage(userMsg.content);
  };

  // P7.2: apply a unified diff block from an assistant message to the backend
  const applyPatch = async (diffText: string, blockId: string) => {
    setPatchApplyingId(blockId);
    setPatchFeedback(prev => ({ ...prev, [blockId]: { ok: false, message: 'Applying…' } }));
    try {
      if (!ragProjectId) {
        throw new Error('Select a project first');
      }
      const res = await fetch(`${API_URL}/api/projects/${ragProjectId}/apply-patch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patch: diffText }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data && data.detail ? data.detail : `HTTP ${res.status}`);
      }
      setPatchFeedback(prev => ({ ...prev, [blockId]: { ok: true, message: data.path ? `Patched ${data.path}` : 'Patch applied' } }));
    } catch (e: any) {
      setPatchFeedback(prev => ({ ...prev, [blockId]: { ok: false, message: e?.message || 'Failed to apply patch' } }));
    } finally {
      setPatchApplyingId(null);
      setTimeout(() => {
        setPatchFeedback(prev => {
          const next = { ...prev };
          delete next[blockId];
          return next;
        });
      }, 4000);
    }
  };

  const toggleFinding = (msgId: string, index: number) => {
    setFindingsSelection(prev => {
      const current = prev[msgId] || [];
      const next = current.includes(index)
        ? current.filter(i => i !== index)
        : [...current, index];
      return { ...prev, [msgId]: next };
    });
  };

  // P7.4: branch the conversation at a given assistant message index
  const branchFromMessage = async (messageIndex: number) => {
    if (!currentChatId) return;
    try {
      const res = await fetch(`${API_URL}/api/chats/${currentChatId}/branch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_index: messageIndex }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data && data.detail ? data.detail : `HTTP ${res.status}`);
      }
      const newChat = await res.json();
      setCurrentChatId(newChat.id);
      setMessages(
        (newChat.messages || []).map((m: any, i: number) => ({
          id: `${newChat.id}-${i}`,
          content: m.content || '',
          role: m.role === 'user' ? ('user' as const) : ('assistant' as const),
          timestamp: new Date(),
        }))
      );
      loadChatList();
    } catch (e: any) {
      console.error('Branch failed:', e);
    }
  };

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: 'user',
      timestamp: new Date()
    };

    setInput('');
    setIsLoading(true);
    setStreamStarted(false);
    setPendingImages([]);

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantMsgId,
      content: '',
      role: 'assistant',
      timestamp: new Date()
    };
    const baseMessages = currentChatId
      ? messages
      : [
          {
            id: 'welcome-' + Date.now(),
            content: "You're starting a new conversation.",
            role: 'assistant' as const,
            timestamp: new Date(),
          },
        ];
    const nextMessages = [...baseMessages, userMessage, assistantMsg];
    setMessages(nextMessages);

    // Persist: create a chat record if needed (auto-titled from the first user message)
    let chatId = currentChatId;
    if (!chatId) {
      try {
        const res = await fetch(`${API_URL}/api/chats`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model,
            messages: [{ role: 'user', content }],
          }),
        });
        const created = await res.json();
        chatId = created.id;
        setCurrentChatId(chatId);
        loadChatList();
      } catch (e) {
        console.error('Failed to create chat record:', e);
      }
    }

    const persistFinal = (finalContent: string) => {
      if (!chatId || !finalContent) return;
      persistChat(chatId, nextMessages.map(m =>
        m.id === assistantMsgId ? { ...m, content: finalContent } : m
      ));
    };

    const setContent = (text: string) => {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMsgId ? { ...msg, content: text } : msg
        )
      );
    };

    let finished = false;
    let fullContent = '';
    let streamError: string | null = null;

    // Reset the no-progress watchdog on every received frame
    let watchdog: ReturnType<typeof setTimeout> | null = null;
    const armWatchdog = (ms: number = 20000) => {
      if (watchdog) clearTimeout(watchdog);
      watchdog = setTimeout(() => {
        // No data for 20 s → model is hung / connection died → fail soft
        streamError = streamError || 'No response from the model — the stream stalled.';
        finish('stall');
      }, ms);
    };

    const finish = (kind: 'done' | 'stop' | 'timeout' | 'stall' = 'done') => {
      if (finished) return;
      finished = true;
      if (watchdog) clearTimeout(watchdog);
      streamRef.current = null;
      setIsLoading(false);
      if (streamError) {
        // Stream/connection error → red card with retry (keep partial text)
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMsgId ? { ...msg, error: streamError! } : msg
        ));
      } else if (kind === 'stop') {
        // User-initiated stop: keep partial text + inline note (no retry)
        if (!fullContent) {
          setMessages(prev => prev.map(msg =>
            msg.id === assistantMsgId ? { ...msg, content: '⏹ — stopped before any text arrived' } : msg
          ));
          fullContent = '⏹ — stopped before any text arrived';
        } else {
          setMessages(prev => prev.map(msg =>
            msg.id === assistantMsgId ? { ...msg, content: fullContent + '\n\n⏹ — generation stopped' } : msg
          ));
          fullContent = fullContent + '\n\n⏹ — generation stopped';
        }
      } else if (kind !== 'done') {
        // Timeout/stall → error card with retry
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMsgId ? { ...msg, error: 'Generation timed out. The model may still be thinking — try again.' } : msg
        ));
      }
      persistFinal(fullContent);
    };

    try {
      // Use SSE streaming for real-time updates
      const fileIds = Array.from(selectedFiles).join(',');
      const params = new URLSearchParams({
        message: content,
        model_name: model,
        file_ids: fileIds,
      });
      // P7.1: send conversation history for multi-turn + tool-call support
      const historyForApi = nextMessages
        .filter(m => m.role === 'user' || (m.role === 'assistant' && m.content && m.id !== assistantMsgId))
        .map(m => ({ role: m.role, content: m.content }));
      if (historyForApi.length > 0) {
        params.set('messages', JSON.stringify(historyForApi));
      }
      // P7.9: send pending image URLs for multimodal input
      if (pendingImages.length > 0) {
        params.set('image_urls', pendingImages.join(','));
      }
      // P3.2: RAG mode active → backend picks the top relevant chunks of the
      // imported project for this question (file_ids still ride along as an
      // explicit selection, but the RAG prefix does the grounding).
      if (ragProjectId) params.set('project_ids', ragProjectId);
      const eventSource = new EventSource(
        `${API_URL}/stream/api/chat?${params.toString()}`
      );

      eventSource.onmessage = (event) => {
        if (event.data === '[DONE]') {
          finish();
          try { eventSource.close(); } catch { /* already closed */ }
          return;
        }
        try {
          const data = JSON.parse(event.data);
          const type = data.type || 'text';

          if (type === 'image') {
            // P7.9: render attached images as part of the message
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId
                ? { ...msg, image_urls: (msg as any).image_urls ? (msg as any).image_urls.concat(data.urls) : data.urls }
                : msg
            ));
            return;
          }

          if (type === 'text' && data.text) {
            if (!streamStarted) {
              setStreamStarted(true);
            }
            armWatchdog();
            fullContent += data.text;
            setContent(fullContent);
          } else if (type === 'compressed' && data.note) {
            setCompressedNote(data.note);
          } else if (type === 'usage' && data.usage) {
            setLastUsage(data.usage);
          } else if (type === 'tool_call') {
            armWatchdog();
            setMessages(prev => ([
              ...prev,
              {
                id: `tool-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                content: '',
                role: 'assistant',
                timestamp: new Date(),
                toolCalls: [{ id: data.id, name: data.name, args: data.args }],
              } as Message
            ]));
          } else if (type === 'tool_result') {
            armWatchdog();
            setMessages(prev => prev.map(msg =>
              (msg.toolCalls && msg.toolCalls.some(tc => tc.id === data.id))
                ? { ...msg, toolResults: { ...(msg.toolResults || {}), [data.id]: data.result } }
                : msg
            ));
          } else if (data.error) {
            streamError = data.error;
            try { eventSource.close(); } catch { /* noop */ }
            finish('done'); // error will be rendered as a card below partial content
          }
        } catch (e) {
          console.error('Failed to parse stream data:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource failed:', error);
        if (finished) return; // Stop/timeout already handled it
        streamError = streamError || 'Lost connection to the model while streaming.';
        try { eventSource.close(); } catch { /* noop */ }
        finish('done');
      };

      // Expose the stream handle so the Stop button can abort mid-stream
      streamRef.current = {
        es: eventSource,
        close: (reason?: 'done' | 'stop' | 'timeout') => {
          try { eventSource.close(); } catch { /* noop */ }
          finish(reason === 'done' ? 'done' : reason || 'stop');
        },
      };

      armWatchdog(30000); // first frame can take longer on a cold model
    } catch (error) {
      console.error('Chat error:', error);
      setContent(
        "❌ Error: Cannot connect to backend. Make sure it's running on http://localhost:8001"
      );
      setIsLoading(false);
    }
  };

  const handleStop = () => {
    // Abort the live stream; partial text is kept + persisted
    streamRef.current?.close('stop');
  };

  const clearChat = () => {
    setCurrentChatId(null);
    setMessages([newChatState()]);
  };

  // ProjectPanel loads/switches/deletes projects: track its file IDs and drop
  // selections that point at files the current project no longer has.
  const handleProjectFiles = (ids: readonly string[]) => {
    const next = new Set<string>(ids);
    const prev = lastProjectFileIds.current;
    const gone = new Set([...prev].filter(id => !next.has(id)));
    setSelectedFiles(s => {
      const out = new Set(s);
      gone.forEach(id => out.delete(id));
      return out;
    });
    lastProjectFileIds.current = next;
  };

  // ── P3.3 code actions ────────────────────────────────────────────────
  // One-click chips above the input bar. Each composes a self-contained
  // prompt template and runs it against the CURRENT context (selected files
  // via file_ids, or the RAG project via project_ids). "Refactor" is
  // free-form: it prefills the input so the user adds the target pattern.
  const codeActions = [
    {
      icon: '💡',
      label: 'Explain this file',
      build: () =>
        'Explain the attached code, file by file. ' +
        'Walk through its structure and purpose, then go through each ' +
        'function/class in order explaining what it does, how its parts ' +
        'interact, and any non-obvious behavior. ' +
        'Cite the file path and function names you refer to. ' +
        'If no code is attached, ask me which file to use.',
    },
    {
      icon: '🧪',
      label: 'Generate unit tests',
      build: () =>
        'Write a comprehensive unit-test suite for the attached code, ' +
        'one code block per file. ' +
        'Cover the happy path, edge cases (empty, null, boundary values), ' +
        'and error handling for every public function or class. ' +
        'Use the same language/framework the code uses and state your ' +
        'assumptions. ' +
        'If no code is attached, ask me which file to use.',
    },
    {
      icon: '🧹',
      label: 'Find dead code',
      build: () =>
        'Review the attached code for dead or unused code. ' +
        'List: (1) unused imports, (2) functions/variables/classes that are ' +
        'never referenced, and (3) unreachable or redundant branches. ' +
        'For each item give the file, line (if identifiable), and why it is ' +
        'likely dead. Then emit a unified diff in a fenced ```diff block that ' +
        'removes the dead code. Keep the diff minimal and safe. ' +
        'Also emit a fenced ```json block with the schema ' +
        '`{"findings":[{"file":"...","line":12,"kind":"unused_import","symbol":"os","fix":"remove"}, ...]}`. ' +
        'If no code is attached, ask me which file(s) to use.',
    },
  ];

  const runCodeAction = (build: () => string) => {
    // The backend picks the top relevant chunks (RAG) or the explicit
    // selected files (file_ids). If neither is attached the action still
    // sends — the prompt template asks the model to request the file — but
    // we nudge toward context so the answer is grounded.
    sendMessage(build());
  };

  // "Refactor" is free-form: prefill the input box and let the user add the
  // target pattern before pressing send.
  const prefillRefactor = () => {
    const target = prompt(
      'What pattern or convention should the attached code be refactored to?\n' +
        '(e.g. "use dataclasses", "extract repeated logic into a helper", "follow SOLID")'
    );
    if (target == null) return; // cancelled → do nothing
    const text =
      'Refactor the attached code to: ' +
      (target.trim() || 'follow clean, conventional best practices') +
      '. Keep the public behavior identical. ' +
      'Emit a unified diff in a fenced ```diff block with the changes, ' +
      'plus a short explanation of what changed and why. ' +
      'If no code is attached, ask me which file to use.';
    setInput(text);
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (el) el.style.height = Math.min(el.scrollHeight, 200) + 'px';
      el?.focus();
    });
  };

  // Phase 4.2: every conversation starts life with a placeholder assistant
  // message (id `welcome` at boot, `welcome-<ts>` after "Clear chat").
  // `messages.length === 1 && isWelcome` = no real user turn exists yet →
  // the empty-state card is the right thing to show. Restored/persisted chats
  // use `${chatId}-${i}` ids instead, so a one-message persisted chat still
  // renders as a normal bubble (unchanged behavior).
  const isWelcome = messages.length === 1 &&
    (messages[0].id === 'welcome' || messages[0].id.startsWith('welcome-'));

  // P7.2: extract fenced ```diff blocks from assistant content
  const extractDiffBlocks = (content: string) => {
    const regex = /```diff\n([\s\S]*?)```/g;
    const blocks: { id: string; text: string }[] = [];
    let m: RegExpExecArray | null;
    let idx = 0;
    while ((m = regex.exec(content)) !== null) {
      blocks.push({ id: `diff-${idx}`, text: m[1].trim() });
      idx++;
    }
    return blocks;
  };

  // P7.3: extract structured findings from fenced ```json blocks that contain
  // a top-level `findings` array (schema v1).
  type Finding = { file?: string; line?: number; kind?: string; symbol?: string; fix?: string };
  const extractFindings = (content: string): { id: string; findings: Finding[] }[] => {
    const regex = /```json\n([\s\S]*?)```/g;
    const out: { id: string; findings: Finding[] }[] = [];
    let m: RegExpExecArray | null;
    let idx = 0;
    while ((m = regex.exec(content)) !== null) {
      try {
        const parsed = JSON.parse(m[1].trim());
        if (Array.isArray(parsed.findings)) {
          out.push({ id: `findings-${idx}`, findings: parsed.findings });
        }
      } catch {
        // skip non-JSON or unrelated json blocks
      }
      idx++;
    }
    return out;
  };

  // Shared by the code-block copy button and the empty-state "ollama pull"
  // snippet: best-effort clipboard write, and while the app is offline the
  // button's title still tells the user what to select-copy.
  const ClipboardCopyButton = ({ text, className, title }: {
    text: string; className: string; title: string;
  }) => (
    <button
      onClick={(e) => {
        const el = e.currentTarget;
        navigator.clipboard?.writeText(text).catch(() => {
          /* clipboard blocked (permissions/https) — text is still selectable */
        });
        const old = el.innerHTML;
        el.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
        setTimeout(() => { el.innerHTML = old; }, 1200);
      }}
      title={title}
      type="button"
      className={className}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
    </button>
  );

  // Theme-aware styles
  const containerBg = theme === 'dark' ? 'bg-slate-950' : 'bg-gray-50';
  const textColor = theme === 'dark' ? 'text-slate-100' : 'text-gray-900';
  const headerBg = theme === 'dark' ? 'bg-slate-950/95' : 'bg-white';
  const borderColor = theme === 'dark' ? 'border-slate-800' : 'border-gray-200';

  return (
    <div className={`min-h-screen ${containerBg} ${textColor} flex`}>
      {/* Chat History — popup (like Settings): overlay, zero inline footprint when closed */}
      {showSidebar && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setShowSidebar(false)}
          />
          <aside
            className={`fixed left-0 top-0 h-full w-full md:w-80 z-50 shadow-xl overflow-y-auto flex flex-col ${
              theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'
            } border-r`}
          >
            <ChatSidebar
              apiUrl={API_URL}
              selectedId={currentChatId}
              onSelect={handleSelectChat}
              onCreate={handleCreateChat}
              onDelete={handleDeleteChat}
            />
            <div className="p-3 border-t mt-auto" style={{ borderColor: theme === 'dark' ? '#1e293b' : '#e5e7eb' }}>
              <button
                onClick={() => handleExportChat('md')}
                disabled={!currentChatId}
                className="w-full p-2 text-sm rounded-lg disabled:opacity-40 hover:bg-slate-800 transition-colors"
              >
                ⬇ Export as Markdown
              </button>
              <button
                onClick={() => handleExportChat('json')}
                disabled={!currentChatId}
                className="w-full p-2 text-sm rounded-lg disabled:opacity-40 mt-1 hover:bg-slate-800 transition-colors"
              >
                ⬇ Export as JSON
              </button>
            </div>
          </aside>
        </>
      )}
      {/* Logs drawer (toggle from header) — like Settings: overlay, only rendered when open */}
      {showLogs && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setShowLogs(false)}
          />
          <div
            className={`fixed bottom-0 left-0 right-0 z-50 shadow-2xl ${
              theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-200'
            } border-t max-h-[70vh] md:max-h-[420px] flex flex-col`}
          >
            <LogsPanel apiUrl={API_URL} theme={theme} onClose={() => setShowLogs(false)} />
          </div>
        </>
      )}

      {/* Settings Sidebar */}
      {showSettings && (
        <>
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setShowSettings(false)}
          />
          <aside
            className={`fixed left-0 top-0 bottom-0 w-full md:w-96 z-50 shadow-xl overflow-y-auto border-r ${
              theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-200'
            }`}
          >
            <SettingsPanel
              apiUrl={API_URL}
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

      {/* Main content column (header + chat) — sits to the right of the sidebar */}
      <div className="flex-1 min-w-0 flex flex-col min-h-screen">
      {/* Header */}
      <header className={`border-b ${borderColor} p-4 sticky top-0 ${headerBg} backdrop-blur z-10`}>
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(v => !v)}
              className={`p-2 rounded-lg transition-colors ${showSidebar ? 'bg-indigo-600 text-white' : 'hover:bg-slate-800'}`}
              title="Toggle chat history"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </svg>
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
              title="Settings"
            >
              <SettingsIcon />
            </button>
            <button
              onClick={() => setShowLogs((v) => !v)}
              className={`p-2 rounded-lg transition-colors ${showLogs ? 'bg-emerald-600 text-white' : 'hover:bg-slate-800'}`}
              title="Runtime logs (live)"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="4 17 10 11 4 5" />
                <line x1="12" y1="19" x2="20" y2="19" />
              </svg>
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
              className={`${theme === 'dark' ? 'bg-slate-900 text-slate-100' : 'bg-slate-100 text-slate-900'} border ${borderColor} rounded-lg px-3 py-2 text-sm hover:border-indigo-500 transition-colors`}
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

            {/* P7.5 token usage budget */}
            {lastUsage && (() => {
              const ctx = 8192;
              const pct = Math.min(lastUsage.total_tokens / ctx, 1);
              const warn = pct > 0.8;
              return (
                <div className="hidden md:flex items-center gap-2 text-xs opacity-80">
                  <div className="w-24 h-1.5 rounded-full overflow-hidden border border-current">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pct * 100}%`, background: warn ? '#f87171' : '#818cf8' }}
                    />
                  </div>
                  <span className={warn ? 'text-rose-500 font-medium' : ''}>
                    {lastUsage.total_tokens.toLocaleString()} / {ctx.toLocaleString()}
                  </span>
                  {warn && <span className="text-rose-500 font-medium">⚠ context nearing limit</span>}
                </div>
              );
            })()}

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
      <main className="w-full max-w-[1100px] mx-auto px-4 pb-32">
        {isWelcome ? (
          <div className="flex flex-col items-center justify-center min-h-[60vh] w-full py-8">
            {/* Ollama reachable (or unknown): the normal start card */}
            {ollamaUp !== false ? (
              <>
                <div className="mb-6">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-indigo-500">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                  </svg>
                </div>
                <h2 className="text-2xl font-semibold mb-2">Start your first conversation</h2>
                <p className="text-center max-w-md mb-8 opacity-70">
                  Attach a file or import your project with the 📎 button, then pick an action —
                  or just ask. Running locally with Ollama — 100% private.
                </p>
                {/* The four code actions, as the primary start points (Phase 4.2).
                    Each sends its prompt with whatever context is attached; with
                    nothing attached the model asks which file to use. */}
                <div className={`grid gap-3 max-w-lg w-full ${theme === 'dark' ? 'text-slate-300' : 'text-gray-600'}`}>
                  {codeActions.map((a) => (
                    <button
                      key={a.label}
                      onClick={() => runCodeAction(a.build)}
                      className={`flex items-center gap-3 p-4 rounded-xl border text-left text-sm transition-colors ${
                        theme === 'dark' ? 'bg-slate-900 border-slate-800 hover:border-indigo-500'
                        : 'bg-white border-gray-200 hover:border-indigo-500'
                      }`}
                    >
                      <span className="text-xl shrink-0">{a.icon}</span>
                      {a.label}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              /* Ollama (or the backend) unreachable: tell the user exactly how
                 to fix it. Copy-safe: the pull command is shown + copyable,
                 never auto-executed (Phase 4.2). */
              <>
                <div className="mb-6">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={theme === 'dark' ? 'text-rose-500' : 'text-rose-500'}>
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                </div>
                <h2 className="text-2xl font-semibold mb-2">Ollama is offline</h2>
                <p className="text-center max-w-md mb-4 opacity-70">
                  CodeForge couldn't reach the model runner. Start it, pull a model if you
                  haven't already, then check again:
                </p>
                <div className={`relative max-w-md w-full mb-6 rounded-xl p-4 text-sm font-mono ${
                  theme === 'dark' ? 'bg-slate-950 border-slate-800 text-slate-300'
                  : 'bg-gray-100 border-gray-200 text-gray-700'
                } border`}>
                  <ClipboardCopyButton
                    text={'ollama serve\nollama pull qwen3:8b'}
                    className={`absolute top-2 right-2 p-1.5 rounded-lg ${
                      theme === 'dark' ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-white hover:bg-gray-200 text-gray-600 shadow'
                    }`}
                    title="Copy setup commands"
                  />
                  <div className="flex flex-col gap-1">
                    <span>$ ollama serve</span>
                    <span>$ ollama pull qwen3:8b</span>
                  </div>
                </div>
                <button
                  onClick={fetchModels}
                  className={`shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    theme === 'dark' ? 'bg-rose-600 hover:bg-rose-500'
                    : 'bg-rose-600 hover:bg-rose-700'
                  } text-white`}
                >
                  Check again
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto pr-2 mb-4 w-full">
            {/* P7.6 context compression banner */}
            {compressedNote && (
              <div className={`p-3 rounded-lg border text-xs ${theme === 'dark' ? 'bg-slate-900 border-slate-700 text-slate-300' : 'bg-white border-gray-200 text-gray-700'}`}>
                {compressedNote}
              </div>
            )}
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
                              
                              // P7.2: diff blocks are rendered below as actionable patch UI
                              if (!inline && match && language === 'diff') {
                                return null;
                              }

                              if (!inline && match) {
                                return (
                                  <div className={`relative my-3 rounded-lg overflow-hidden`}>
                                    <div className={`w-full ${theme === 'dark' ? 'bg-slate-950' : 'bg-gray-100'}`}>
                                      <SyntaxHighlighter
                                    language={language}
                                        style={theme === 'dark' ? oneDark : oneLight}
                                        showLineNumbers={codeText.split('\n').length > 4}
                                        customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '0.8rem' }}
                                        codeTagProps={{ style: { background: 'transparent', fontFamily: 'inherit' } }}
                                        lineNumberStyle={{ opacity: 0.4, paddingRight: '1rem', minWidth: '2.5rem', textAlign: 'right' }}
                                      >
                                        {codeText}
                                      </SyntaxHighlighter>
                                    </div>
                                    <ClipboardCopyButton
                                      className={`absolute top-2 right-2 p-2 rounded-lg transition-colors ${theme === 'dark' ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-white hover:bg-gray-200 text-gray-600 shadow'}`}
                                      text={codeText}
                                      title="Copy code"
                                    />
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
                        {/* P7.9: render attached images */}
                        {(msg as any).image_urls && (msg as any).image_urls.length > 0 && (
                          <div className="mt-3 flex gap-2 flex-wrap">
                            {(msg as any).image_urls.map((url: string) => (
                              <img key={url} src={`${API_URL}${url}`} alt="" className="max-h-64 rounded-lg border border-gray-300 dark:border-slate-700 object-contain" />
                            ))}
                          </div>
                        )}
                        {/* P7.1 tool-call cards */}
                        {msg.toolCalls && msg.toolCalls.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {msg.toolCalls.map(tc => (
                              <div key={tc.id} className={`p-3 rounded-lg border ${
                                theme === 'dark' ? 'bg-slate-950 border-slate-700' : 'bg-gray-50 border-gray-200'
                              }`}>
                                <div className="flex items-center gap-2 text-sm font-medium">
                                  <span>🔧</span>
                                  <span>{tc.name}</span>
                                </div>
                                <pre className="mt-2 text-xs font-mono opacity-70 overflow-x-auto">
                                  {JSON.stringify(tc.args, null, 2)}
                                </pre>
                                {msg.toolResults?.[tc.id] !== undefined && (
                                  <div className={`mt-2 p-2 rounded border text-xs font-mono ${
                                    theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'
                                  }`}>
                                    <div className="opacity-70 mb-1">Result:</div>
                                    <pre className="whitespace-pre-wrap break-words">
                                      {typeof msg.toolResults[tc.id] === 'string'
                                        ? msg.toolResults[tc.id]
                                        : JSON.stringify(msg.toolResults[tc.id], null, 2)}
                                    </pre>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                        {/* Error card with retry */}
                        {msg.error && (
                          <div className="mt-3 p-3 rounded-lg border border-rose-500/50 bg-rose-500/10">
                            <div className="text-sm text-rose-500 font-medium">Error</div>
                            <div className="text-sm mt-1 whitespace-pre-wrap">{msg.error}</div>
                            <button
                              onClick={retryLastMessage}
                              className="mt-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition-colors"
                            >
                              Retry
                            </button>
                          </div>
                        )}
                        {/* P7.2 actionable diff blocks */}
                        {(() => {
                          const blocks = extractDiffBlocks(msg.content || '');
                          if (blocks.length === 0) return null;
                          return (
                            <div className="mt-3 space-y-2">
                              {blocks.map(block => {
                                const feedback = patchFeedback[block.id];
                                const applying = patchApplyingId === block.id;
                                return (
                                  <div key={block.id} className={`p-3 rounded-lg border ${theme === 'dark' ? 'bg-slate-950 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="text-xs font-medium opacity-70">Unified diff</span>
                                      <button
                                        onClick={() => applyPatch(block.text, block.id)}
                                        disabled={applying || !ragProjectId}
                                        className={`shrink-0 px-2 py-1 rounded text-xs font-medium transition-colors ${applying || !ragProjectId ? 'opacity-50 cursor-not-allowed' : theme === 'dark' ? 'bg-indigo-600 hover:bg-indigo-500 text-white' : 'bg-indigo-600 hover:bg-indigo-700 text-white'}`}
                                      >
                                        {applying ? 'Applying…' : (!ragProjectId ? 'Select project' : 'Apply patch')}
                                      </button>
                                    </div>
                                    {feedback && (
                                      <div className={`mt-2 text-xs ${feedback.ok ? 'text-emerald-500' : 'text-rose-500'}`}>{feedback.message}</div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          );
                        })()}
                        {/* P7.3 structured findings list */}
                        {(() => {
                          const findingsGroups = extractFindings(msg.content || '');
                          if (findingsGroups.length === 0) return null;
                          return (
                            <div className="mt-3 space-y-2">
                              {findingsGroups.map(group => {
                                const selected = findingsSelection[msg.id] || [];
                                const allSelected = group.findings.length > 0 && selected.length === group.findings.length;
                                return (
                                  <div key={group.id} className={`p-3 rounded-lg border ${theme === 'dark' ? 'bg-slate-950 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
                                    <div className="flex items-center justify-between gap-2 mb-2">
                                      <span className="text-xs font-medium opacity-70">Findings ({group.findings.length})</span>
                                      <button
                                        onClick={() => setFindingsSelection(prev => ({ ...prev, [msg.id]: allSelected ? [] : Array.from({ length: group.findings.length }, (_, i) => i) }))}
                                        className="shrink-0 px-2 py-1 rounded text-xs font-medium transition-colors border border-current opacity-70 hover:opacity-100"
                                      >
                                        {allSelected ? 'Deselect all' : 'Select all'}
                                      </button>
                                    </div>
                                    <div className="space-y-1">
                                      {group.findings.map((f, idx) => {
                                        const checked = selected.includes(idx);
                                        return (
                                          <label key={idx} className={`flex items-start gap-2 text-xs p-2 rounded border cursor-pointer transition-colors ${checked ? (theme === 'dark' ? 'bg-slate-900 border-indigo-500/50' : 'bg-white border-indigo-500/50') : theme === 'dark' ? 'bg-slate-950 border-slate-800' : 'bg-white border-gray-200'}`}>
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={() => toggleFinding(msg.id, idx)}
                                              className="mt-0.5"
                                            />
                                            <span className="flex-1">
                                              <span className="font-medium">{f.kind || 'unknown'}</span>
                                              {f.symbol ? <span className="opacity-70 ml-1">{String(f.symbol)}</span> : null}
                                              {f.file ? <span className="opacity-50 ml-1">{String(f.file)}{f.line != null ? `:${String(f.line)}` : ''}</span> : null}
                                            </span>
                                          </label>
                                        );
                                      })}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          );
                        })()}
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    )}
                    <div className={`text-xs mt-2 ${isAssistant ? 'opacity-50' : 'opacity-75'}`}>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      {isAssistant && currentChatId && (
                        <button
                          onClick={() => branchFromMessage(i)}
                          className="ml-3 underline opacity-70 hover:opacity-100"
                          title="Branch conversation here"
                        >
                          Branch here
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>
      </div>

      {/* Context panels (toggled + cycled from the 📎 button): uploaded files / imported projects */}
      {contextTab !== null && (
        <div className={`fixed left-0 right-0 bottom-[84px] z-30 ${theme === 'dark' ? 'bg-slate-950/95' : 'bg-gray-50/95'} backdrop-blur border-t ${borderColor}`}>
          <div className="max-w-6xl mx-auto p-4">
            {contextTab === 'files' ? (
              <FileContext
                uploadedFiles={uploadedFiles}
                setUploadedFiles={setUploadedFiles}
                selectedFiles={selectedFiles}
                setSelectedFiles={setSelectedFiles}
                theme={theme}
              />
            ) : (
              <ProjectPanel
                selectedFiles={selectedFiles}
                setSelectedFiles={setSelectedFiles}
                theme={theme}
                onFilesChange={handleProjectFiles}
                ragProjectId={ragProjectId}
                setRagProjectId={setRagProjectId}
              />
            )}
            <button
              onClick={() => setContextTab(null)}
              className="mt-3 w-full p-2 text-sm rounded-lg opacity-70 hover:opacity-100 transition-opacity"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className={`fixed bottom-0 left-0 right-0 border-t ${borderColor} ${headerBg} px-4 pt-2 pb-4`}>
        <div className="max-w-6xl mx-auto">
          {/* P3.3 code actions — one-click chips above the input bar. They run
              against whatever context is attached (selected files or the RAG
              project). Compact + horizontally scrollable so they never push the
              input off-screen. */}
          <div className="flex gap-2 overflow-x-auto no-scrollbar mb-2 pb-1 -mx-1 px-1" style={{ scrollbarWidth: 'none' }}>
            {codeActions.map((a) => (
              <button
                key={a.label}
                onClick={() => runCodeAction(a.build)}
                disabled={isLoading}
                className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${theme === 'dark' ? 'bg-slate-900 border-slate-700 hover:border-indigo-500 hover:text-indigo-300 text-slate-300' : 'bg-white border-gray-200 hover:border-indigo-500 hover:text-indigo-600 text-gray-600'} disabled:opacity-40 disabled:cursor-not-allowed`}
                title={a.label}
              >
                <span>{a.icon}</span>
                {a.label}
              </button>
            ))}
            <button
              onClick={prefillRefactor}
              disabled={isLoading}
              className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${theme === 'dark' ? 'bg-slate-900 border-slate-700 hover:border-indigo-500 hover:text-indigo-300 text-slate-300' : 'bg-white border-gray-200 hover:border-indigo-500 hover:text-indigo-600 text-gray-600'} disabled:opacity-40 disabled:cursor-not-allowed`}
              title="Refactor to a pattern…"
            >
              <span>🔁</span>
              Refactor…
            </button>
          </div>
        </div>
        <div className="max-w-6xl mx-auto flex items-center gap-2">
          {/* Context button — cycles: attach files → import project → close */}
          <button
            onClick={() =>
              setContextTab(t => t === null ? 'files' : t === 'files' ? 'projects' : null)
            }
            className={`shrink-0 p-3 rounded-xl transition-colors ${
              contextTab === null ? (theme === 'dark' ? 'hover:bg-slate-800' : 'hover:bg-gray-100')
                : (theme === 'dark' ? 'bg-indigo-600 text-white' : 'bg-indigo-600 text-white')
            }`}
            title={
              contextTab === null ? 'Attach code files or import a project'
              : contextTab === 'files' ? 'Switch to imported projects'
              : 'Close the context panel'
            }
          >
            {uploadedFiles.length > 0 ? (
              <span className="flex items-center gap-1.5 text-sm font-medium">
                📎 {selectedFiles.size}
              </span>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="opacity-60">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
              </svg>
            )}
          </button>

          {/* P7.8: prompt templates palette toggle */}
          <button
            onClick={() => setShowSkillPalette(v => !v)}
            className={`shrink-0 p-3 rounded-xl transition-colors ${showSkillPalette ? (theme === 'dark' ? 'bg-indigo-600 text-white' : 'bg-indigo-600 text-white') : (theme === 'dark' ? 'hover:bg-slate-800' : 'hover:bg-gray-100')}`}
            title="Prompt templates"
          >
            <span className="text-sm font-medium">📝</span>
          </button>

          {showSkillPalette && (
            <div className={`absolute bottom-16 right-4 z-50 w-72 max-h-64 overflow-y-auto rounded-xl border shadow-2xl ${theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-white border-gray-200'}`}>
              <div className="p-2 border-b border-current opacity-70 text-xs font-medium">Prompt templates</div>
              {skills.length === 0 && (
                <div className="p-3 text-xs opacity-50">No templates yet.</div>
              )}
              {skills.map(s => (
                <button
                  key={s.name}
                  onClick={() => insertSkill(s.body)}
                  className={`w-full text-left px-3 py-2 text-xs border-b border-current opacity-80 hover:opacity-100 transition-colors last:border-0 ${theme === 'dark' ? 'border-slate-800' : 'border-gray-100'}`}
                  title={s.model_override ? `Model override: ${s.model_override}` : undefined}
                >
                  <div className="font-medium">{s.title}</div>
                  <div className="opacity-50">/{s.name}</div>
                </button>
              ))}
            </div>
          )}

          {/* Thinking indicator: only while waiting for the first token */}
          {isLoading && !streamStarted && (
            <div className="flex items-center gap-2 opacity-70 px-1">
              <span className="inline-flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce"
                    style={{ animationDelay: `${i * 0.18}s` }}
                  />
                ))}
              </span>
              <span className="text-xs whitespace-nowrap">Thinking…</span>
            </div>
          )}

          {/* Input + send grouped: the field always takes the full remaining
              width; send sits flush at the right edge — no left dead-zone. */}
          <div className="flex-1 flex items-end gap-2 min-w-0">
            <textarea
              rows={1}
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // auto-grow (capped): Shift+Enter produces real newlines
                const el = e.target;
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 200) + 'px';
              }}
              onPaste={async (e) => {
                const items = Array.from(e.clipboardData?.items || []);
                const imageItems = items.filter(it => it.type.startsWith('image/'));
                if (imageItems.length > 0) {
                  e.preventDefault();
                  await uploadImages(imageItems.map(it => it.getAsFile()).filter(Boolean) as File[]);
                }
              }}
              onDragOver={(e) => { e.preventDefault(); }}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files.length > 0) {
                  uploadImages(e.dataTransfer.files);
                }
              }}
              onKeyDown={(e) => {
                // Enter = send, Shift+Enter = newline (Phase 4.2)
                if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
                  const trimmed = input.trim();
                  // P7.8: slash command expansion
                  if (trimmed.startsWith('/')) {
                    const name = trimmed.slice(1).split(/\s+/)[0];
                    const skill = skills.find(s => s.name === name);
                    if (skill) {
                      e.preventDefault();
                      insertSkill(skill.body);
                      return;
                    }
                  }
                  e.preventDefault();
                  sendMessage(input);
                }
              }}
              placeholder="Type your message..."
              disabled={isLoading}
              className={`flex-1 min-w-0 resize-none ${theme === 'dark' ? 'bg-slate-900 border-slate-700' : 'bg-gray-50 border-gray-200'} border rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 transition-colors`}
            />
            {pendingImages.length > 0 && (
              <div className="flex gap-2 px-4 pt-2 flex-wrap">
                {pendingImages.map(url => (
                  <div key={url} className="relative inline-block">
                    <img src={`${API_URL}${url}`} alt="" className="h-16 rounded-lg border border-gray-300 dark:border-slate-700 object-cover" />
                    <button
                      onClick={() => removePendingImage(url)}
                      className="absolute -top-2 -right-2 w-5 h-5 bg-gray-800 text-white rounded-full text-xs flex items-center justify-center"
                      title="Remove"
                    >×</button>
                  </div>
                ))}
              </div>
            )}

            {isLoading ? (
              <button
                onClick={handleStop}
                className={`shrink-0 p-3 bg-rose-600 hover:bg-rose-700 rounded-xl transition-colors flex items-center justify-center min-w-[48px] ${!streamStarted ? '' : ''}`}
                title="Stop generation"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                onClick={() => sendMessage(input)}
                disabled={!input.trim()}
                className="shrink-0 p-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-colors flex items-center justify-center min-w-[48px] text-white"
              >
                <SendIcon />
              </button>
            )}
            <label className="shrink-0 p-3 bg-gray-200 dark:bg-slate-800 hover:bg-gray-300 dark:hover:bg-slate-700 rounded-xl transition-colors flex items-center justify-center min-w-[48px] cursor-pointer" title="Attach image">
              <input
                type="file"
                accept="image/png,image/jpg,image/jpeg,image/gif,image/webp,image/svg+xml"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    uploadImages(e.target.files);
                    e.target.value = '';
                  }
                }}
              />
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
