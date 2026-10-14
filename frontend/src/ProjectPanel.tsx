'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

// Hard cap = backend's own cap in add_file_context (file_ids[:5]).
const MAX_CONTEXT_FILES = 5;

interface ProjectFileMeta {
  id: string;
  path: string;
  size: number;
  line_count?: number;
}

interface ProjectMeta {
  id: string;
  name: string;
  file_count: number;
  files?: ProjectFileMeta[];
}

interface Props {
  selectedFiles: Set<string>;
  setSelectedFiles: React.Dispatch<React.SetStateAction<Set<string>>>;
  theme: 'dark' | 'light';
  /** Called with the current project's file IDs after load/switch/delete so
      the app can drop their stale selections/counts. */
  onFilesChange?: (fileIds: readonly string[]) => void;
}

interface DirNode {
  name: string;
  dirs: Map<string, DirNode>;
  files: ProjectFileMeta[];
}

function buildTree(files: ProjectFileMeta[]): DirNode {
  const root: DirNode = { name: '', dirs: new Map(), files: [] };
  for (const f of files) {
    const parts = f.path.split('/').filter(Boolean);
    const fname = parts.pop()!; // always ≥1 part (path never blank)
    const dirPath = parts.join('/');
    const dir = dirPath ? insertDir(root, dirPath.split('/')) : root;
    dir.files.push({ ...f, path: fname });
  }
  return root;
}

function insertDir(root: DirNode, parts: string[]): DirNode {
  let node = root;
  for (const part of parts) {
    let next = node.dirs.get(part);
    if (!next) {
      next = { name: part, dirs: new Map(), files: [] };
      node.dirs.set(part, next);
    }
    node = next;
  }
  return node;
}

function sortNode(node: DirNode) {
  [...node.dirs.values()].sort((a, b) => a.name.localeCompare(b.name));
  node.dirs.forEach(n => sortNode(n));
  node.files.sort((a, b) => a.path.localeCompare(b.path));
}

function formatSize(bytes: number | string) {
  const n = typeof bytes === 'string' ? parseFloat(bytes) : bytes;
  if (!Number.isFinite(n) || n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() || '';
  const icons: Record<string, string> = {
    js: '📜', jsx: '⚛️', ts: '🔷', tsx: '⚛️',
    py: '🐍', java: '☕', go: '🐹', rs: '⚙️',
    html: '🌐', css: '🎨', json: '📋', md: '📝',
  };
  return icons[ext] || '📄';
}

function ProjectTree({
  node,
  pathPrefix,
  selectedFiles,
  toggle,
  theme,
}: {
  node: DirNode;
  pathPrefix: string;
  selectedFiles: Set<string>;
  toggle: (id: string) => void;
  theme: 'dark' | 'light';
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const flip = (key: string) =>
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });

  return (
    <div className="pl-2">
      {[...node.dirs.values()].map(dir => {
        const key = pathPrefix + dir.name;
        const open = !collapsed.has(key);
        return (
          <div key={key}>
            <button
              type="button"
              onClick={() => flip(key)}
              className={`w-full flex items-center gap-1.5 py-1.5 px-2 rounded-lg text-left transition-colors ${
                theme === 'dark' ? 'hover:bg-slate-800/60 text-slate-200' : 'hover:bg-gray-100 text-gray-800'
              }`}
              title={`${key}/ (click to ${open ? 'collapse' : 'expand'})`}
            >
              <span className="w-4 text-xs opacity-60 text-left">{open ? '▾' : '▸'}</span>
              <span className="text-base">📁</span>
              <span className="text-sm font-medium truncate">{dir.name}</span>
              <span className={`ml-auto text-xs ${theme === 'dark' ? 'text-slate-500' : 'text-gray-400'}`}>
                {dir.files.length ? `${dir.files.length} file${dir.files.length > 1 ? 's' : ''}` : ''}
              </span>
            </button>
            {open && <ProjectTree node={dir} pathPrefix={`${key}/`} selectedFiles={selectedFiles} toggle={toggle} theme={theme} />}
          </div>
        );
      })}
      {node.files.map(f => {
        const full = pathPrefix + f.path;
        const checked = selectedFiles.has(f.id);
        return (
          <label
            key={f.id}
            className={`flex items-center gap-2 pl-6 pr-2 py-1.5 rounded-lg cursor-pointer transition-colors ${
              checked
                ? theme === 'dark' ? 'bg-indigo-600/20' : 'bg-indigo-50'
                : theme === 'dark' ? 'hover:bg-slate-800/50' : 'hover:bg-gray-100'
            }`}
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() => toggle(f.id)}
              className="rounded"
            />
            <span className="text-base">{fileIcon(f.path)}</span>
            <span className={`flex-1 min-w-0 truncate text-sm ${theme === 'dark' ? 'text-slate-200' : 'text-gray-700'}`} title={full}>
              {f.path}
            </span>
            <span className={`text-xs shrink-0 ${theme === 'dark' ? 'text-slate-500' : 'text-gray-400'}`}>
              {formatSize(f.size)}
            </span>
          </label>
        );
      })}
    </div>
  );
}

export default function ProjectPanel({ selectedFiles, setSelectedFiles, theme, onFilesChange }: Props) {
  const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8001';
  const zipInputRef = useRef<HTMLInputElement>(null);

  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [active, setActive] = useState<{ id: string; name: string } | null>(null);
  const [activeFiles, setActiveFiles] = useState<ProjectFileMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const flashTimer = (msg: string) => {
    setFlash(msg);
    setTimeout(() => setFlash(null), 4000);
  };

  const loadProjectFiles = useCallback(async (p: ProjectMeta) => {
    const res = await fetch(`${API_URL}/api/projects/${p.id}`);
    if (!res.ok) throw new Error(res.statusText);
    const d = await res.json();
    const files: ProjectFileMeta[] = d.files || [];
    setActiveFiles(files);
    onFilesChange?.(files.map(f => f.id));
  }, [API_URL, onFilesChange]);

  const loadProjects = useCallback(async () => {
    const res = await fetch(`${API_URL}/api/projects`);
    if (!res.ok) throw new Error(res.statusText);
    const d = await res.json();
    const list: ProjectMeta[] = d.projects || [];
    setProjects(list);
    if (list.length > 0) {
      setActive({ id: list[0].id, name: list[0].name });
      await loadProjectFiles(list[0]);
    } else {
      setActive(null);
      setActiveFiles([]);
    }
  }, [API_URL, loadProjectFiles]);

  useEffect(() => {
    loadProjects().catch((e) => {
      console.error('Failed to load projects:', e);
      setError('Could not load projects — is the backend running?');
    });
  }, [loadProjects]);

  const selectProject = async (p: ProjectMeta) => {
    setLoading(true);
    setError(null);
    try {
      setActive({ id: p.id, name: p.name });
      await loadProjectFiles(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load project');
    } finally {
      setLoading(false);
    }
  };

  const importZip = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('zip', file);
      const res = await fetch(`${API_URL}/api/projects`, { method: 'POST', body: fd });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(d.detail || `Import failed (${res.status})`);
      } else {
        flashTimer(`Imported "${d.name}" — ${d.file_count} file${d.file_count === 1 ? '' : 's'}`);
        await loadProjects();
        setActive({ id: d.id, name: d.name });
        await loadProjectFiles({ id: d.id, name: d.name, file_count: d.file_count });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Zip import failed');
    } finally {
      setLoading(false);
    }
  };

  const importFolder = async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const files = Array.from(list);
    const firstPath = files[0].webkitRelativePath || files[0].name;
    const name = firstPath.split('/')[0] || 'imported-folder';
    setLoading(true);
    setError(null);
    try {
      // 2 MB per-file cap mirrors the backend limit — skip (not import) oversized
      // files so a single huge build artifact can't block the whole folder.
      const eligible = files.filter(f =>
        f.size <= 2 * 1024 * 1024 &&
        !/node_modules|\.git|__pycache__|\.venv|venv|dist|build/.test(f.webkitRelativePath || ''));
      if (eligible.length === 0) {
        throw new Error('No importable files in that folder (code/text files only)');
      }
      const body = {
        name,
        files: await Promise.all(eligible.map(async f => ({
          path: f.webkitRelativePath || f.name,
          content: await f.text(),
        }))),
      };
      const res = await fetch(`${API_URL}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(d.detail || `Import failed (${res.status})`);
      }
      flashTimer(`Imported "${d.name}" — ${d.file_count} file${d.file_count === 1 ? '' : 's'}`);
      await loadProjects();
      setActive({ id: d.id, name: d.name });
      await loadProjectFiles({ id: d.id, name: d.name, file_count: d.file_count });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Folder import failed');
    } finally {
      setLoading(false);
    }
  };

  const deleteProject = async (p: ProjectMeta) => {
    // Drop this project's file IDs from the shared selection BEFORE switching,
    // while activeFiles still describes the deleted project.
    const removed = new Set(activeFiles.map(f => f.id));
    setSelectedFiles(prev => {
      const next = new Set(prev);
      removed.forEach(id => next.delete(id));
      return next;
    });
    const res = await fetch(`${API_URL}/api/projects/${p.id}`, { method: 'DELETE' });
    if (!res.ok) {
      setError('Delete failed');
      return;
    }
    // selection only references this project's files if they were checked — drop them
    setSelectedFiles(prev => {
      const next = new Set(prev);
      for (const f of activeFiles) if (f.id && f.id.startsWith(p.id.slice(0, 4)) === false && next.has(f.id)) next.delete(f.id);
      return next;
    });
    const list = projects.filter(x => x.id !== p.id);
    setProjects(list);
    if (active?.id === p.id) {
      if (list.length > 0) {
        const next = list[0];
        setActive({ id: next.id, name: next.name });
        void loadProjectFiles(next);
      } else {
        setActive(null);
        setActiveFiles([]);
        onFilesChange?.([]);
      }
    }
  };

  const toggle = (fileId: string) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        if (next.size >= MAX_CONTEXT_FILES) {
          flashTimer(`Context cap is ${MAX_CONTEXT_FILES} files — deselect one first`);
          return prev;
        }
        next.add(fileId);
      }
      return next;
    });
  };

  const addAll = () => {
    const room = MAX_CONTEXT_FILES - selectedFiles.size;
    if (room <= 0) {
      flashTimer(`Context cap is ${MAX_CONTEXT_FILES} files — deselect one first`);
      return;
    }
    setSelectedFiles(prev => {
      const next = new Set(prev);
      for (const f of activeFiles) {
        if (next.size >= MAX_CONTEXT_FILES) break;
        next.add(f.id);
      }
      return next;
    });
  };

  const clearProjectSelection = () => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      for (const f of activeFiles) next.delete(f.id);
      return next;
    });
  };

  const selectedInProject = activeFiles.filter(f => selectedFiles.has(f.id)).length;

  const boxCls = theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-gray-50 border-gray-200';
  const subText = theme === 'dark' ? 'text-slate-400' : 'text-gray-500';
  const muted = theme === 'dark' ? 'text-slate-500' : 'text-gray-400';

  if (!active) {
    return (
      <div className={`rounded-xl border p-6 text-center ${boxCls}`}>
        <div className="text-4xl mb-3">🗂️</div>
        <p className={`font-medium mb-1 ${theme === 'dark' ? 'text-slate-200' : 'text-gray-700'}`}>
          No projects imported yet
        </p>
        <p className={`text-sm mb-4 ${subText}`}>
          Import a whole folder as one project — pick individual files for context.
        </p>
        <input
          ref={zipInputRef}
          type="file"
          accept="application/zip,.zip"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0] || null;
            if (f) void importZip(f);
            e.target.value = '';
          }}
        />
        <div className="flex flex-wrap gap-2 justify-center">
          <button
            onClick={() => zipInputRef.current?.click()}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm transition-colors"
          >
            {loading ? 'Working…' : '⬆ Upload a zip'}
          </button>
          <label
            className={`px-4 py-2 rounded-lg text-sm cursor-pointer transition-colors ${
              theme === 'dark' ? 'bg-slate-800 hover:bg-slate-700 text-slate-100' : 'bg-gray-200 hover:bg-gray-300 text-gray-800'
            }`}
          >
            📁 Choose a folder
            <input
              type="file"
              multiple
              // @ts-expect-error — non-standard folder-picker attribute
              webkitdirectory=""
              directory
              className="hidden"
              onChange={(e) => {
                void importFolder(e.target.files);
                e.target.value = '';
              }}
            />
          </label>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border ${boxCls}`}>
      {/* Header */}
      <div className={`p-3 border-b flex flex-wrap items-center gap-2 ${theme === 'dark' ? 'border-slate-800' : 'border-gray-200'}`}>
        {projects.length > 1 ? (
          <select
            value={active.id}
            onChange={(e) => {
              const p = projects.find(x => x.id === e.target.value);
              if (p) void selectProject(p);
            }}
            className={`text-sm rounded-lg px-2 py-1.5 border ${theme === 'dark' ? 'bg-slate-800 border-slate-700 text-slate-100' : 'bg-white border-gray-300 text-gray-800'}`}
            title="Switch project"
          >
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        ) : (
          <span className={`text-sm font-medium ${theme === 'dark' ? 'text-slate-200' : 'text-gray-700'}`}>
            🗂️ {active.name}
          </span>
        )}
        <span className={`ml-auto text-xs ${muted}`}>
          {selectedInProject} of {activeFiles.length} selected
        </span>
        <button
          onClick={addAll}
          disabled={loading || selectedFiles.size >= MAX_CONTEXT_FILES || activeFiles.length === 0}
          className={`text-xs px-2.5 py-1.5 rounded-lg disabled:opacity-40 transition-colors ${
            theme === 'dark' ? 'bg-slate-800 hover:bg-slate-700 text-slate-100' : 'bg-gray-200 hover:bg-gray-300 text-gray-800'
          }`}
          title={`Select up to ${MAX_CONTEXT_FILES} files for the next message`}
        >
          Add all {selectedInProject}/{activeFiles.length}
        </button>
        {selectedInProject > 0 && (
          <button
            onClick={clearProjectSelection}
            className={`text-xs px-2 py-1.5 rounded-lg transition-colors ${
              theme === 'dark' ? 'text-slate-400 hover:text-rose-400' : 'text-gray-500 hover:text-rose-500'
            }`}
          >
            Deselect
          </button>
        )}
        <button
          onClick={() => {
            if (window.confirm(`Delete project "${active.name}" and its ${activeFiles.length} imported files?`)) {
              const p = projects.find(x => x.id === active!.id);
              if (p) void deleteProject(p);
            }
          }}
          className={`text-xs px-2 py-1.5 rounded-lg transition-colors ${
            theme === 'dark' ? 'text-slate-400 hover:text-rose-400' : 'text-gray-500 hover:text-rose-500'
          }`}
          title="Delete this imported project"
        >
          🗑
        </button>
      </div>

      {/* Import-more + status */}
      <div className={`px-3 pt-2 flex flex-wrap items-center gap-2 text-xs ${muted}`}>
        <input
          ref={zipInputRef}
          type="file"
          accept="application/zip,.zip"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0] || null;
            if (f) void importZip(f);
            e.target.value = '';
          }}
        />
        <button
          onClick={() => zipInputRef.current?.click()}
          disabled={loading}
          className="hover:underline disabled:opacity-50"
        >
          + import more (zip)
        </button>
        {loading && <span>importing…</span>}
      </div>
      {error && (
        <div className="mx-3 mt-2 p-2 rounded-lg bg-rose-500/10 text-rose-500 text-sm">⚠️ {error}</div>
      )}
      {flash && (
        <div className={`mx-3 mt-2 p-2 rounded-lg text-sm ${theme === 'dark' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-emerald-50 text-emerald-600'}`}>
          {flash}
        </div>
      )}

      {/* File tree */}
      <div className="max-h-64 overflow-y-auto p-2">
        {activeFiles.length === 0 ? (
          <p className={`text-center text-sm py-6 ${subText}`}>No importable files in this project.</p>
        ) : (
          (() => {
            const tree = buildTree(activeFiles);
            sortNode(tree);
            return (
              <ProjectTree
                node={tree}
                pathPrefix=""
                selectedFiles={selectedFiles}
                toggle={toggle}
                theme={theme}
              />
            );
          })()
        )}
      </div>
    </div>
  );
}
