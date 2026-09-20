import { useState } from 'react';

export default function App() {
  const [input, setInput] = useState('');
  const [theme, setTheme] = useState<'dark'|'light'>(() => (
    localStorage.getItem('jev-theme') as 'dark' | 'light' || 'dark'
  ));

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem('jev-theme', next);
  };

  const sendMessage = () => {
    console.log('Message sent:', input);
    setInput('');
  };

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-black text-slate-200' : 'bg-gray-50 text-gray-900'}`}>
      <header className={`sticky top-0 backdrop-blur-md border-b border-opacity-60 transition-colors ${
        theme === 'dark' ? 'border-slate-800 bg-black/80 text-slate-200 hover:bg-slate-900/50' : 'border-gray-300 bg-white text-gray-900 hover:bg-gray-50/50'
      }`}>
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent animate-gradient">CodeForge AI</h1>
          <button onClick={toggleTheme} className={`p-2 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
            theme === 'dark' ? 'text-yellow-400 hover:bg-slate-800/70 active:scale-95' : 'text-indigo-600 hover:bg-gray-100 active:scale-95'
          }`}>
            { theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode' }
          </button>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 pb-32 flex flex-col justify-center min-h-[calc(100%-7rem)]">
        <p>Welcome to CodeForge AI. Your data stays local.</p>
      </main>
      <div className={`fixed bottom-0 left-0 right-0 backdrop-blur-md border-t z-10 transition-colors ${
        theme === 'dark' ? 'border-slate-800 bg-black/95 text-slate-200 placeholder-slate-600' : 'border-gray-200 bg-white/95 text-gray-900 placeholder-gray-400'
      }`}>
        <div className="max-w-3xl mx-auto px-4 flex gap-3">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyPress={e => {
              if (e.key === 'Enter') { e.preventDefault(); sendMessage(); }
            }}
            rows={2}
            placeholder="Type your message..."
            className={`flex-1 rounded-xl px-4 py-3 resize-none focus:outline-none focus:border-indigo-500 transition-colors ${
              theme === 'dark' ? 'bg-slate-900 border-slate-700 hover:border-slate-600 placeholder-slate-600' : 'bg-gray-50 border-gray-200 hover:border-indigo-400 placeholder-gray-400'
            }`}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim()}
            className={`px-6 py-3 rounded-xl flex items-center gap-2 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
              input.trim() ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white hover:opacity-90 shadow-sm' : theme === 'dark' ? 'bg-slate-950 text-slate-600 cursor-not-allowed border border-slate-800' : 'bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200'
            }`}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
