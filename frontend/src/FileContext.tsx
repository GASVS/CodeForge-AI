'use client';

import { useState, useRef } from 'react';

interface UploadedFile {
  id: string;
  filename: string;
  size: number;
}

interface Props {
  uploadedFiles: UploadedFile[];
  setUploadedFiles: React.Dispatch<React.SetStateAction<UploadedFile[]>>;
  selectedFiles: Set<string>;
  setSelectedFiles: React.Dispatch<React.SetStateAction<Set<string>>>;
  theme: 'dark' | 'light';
}

export default function FileContext({ 
  uploadedFiles, 
  setUploadedFiles, 
  selectedFiles, 
  setSelectedFiles,
  theme
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
    // Limit to 10 files max
    const filesToUpload = Array.from(files).slice(0, Math.max(0, 10 - uploadedFiles.length));
    
    const formData = new FormData();
    filesToUpload.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      setUploadedFiles(prev => [...prev, ...data.files]);
    } catch (error) {
      console.error('File upload error:', error);
      alert(`Failed to upload files: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const toggleFileSelection = (fileId: string) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) {
        next.delete(fileId);
      } else {
        next.add(fileId);
      }
      return next;
    });
  };

  const clearAllFiles = async () => {
    try {
      await fetch(`${API_URL}/api/files`, { method: 'DELETE' });
      setUploadedFiles([]);
      setSelectedFiles(new Set());
    } catch (error) {
      console.error('Clear files error:', error);
    }
  };

  const getFileIcon = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase();
    const icons: Record<string, string> = {
      js: '📜', jsx: '⚛️', ts: '🔷', tsx: '⚛️',
      py: '🐍', java: '☕', go: '🐹', rs: '⚙️',
      html: '🌐', css: '🎨', json: '📋', md: '📝',
    };
    return icons[ext || ''] || '📄';
  };

  const formatSize = (bytes: string | number) => {
    const bytesNum = typeof bytes === 'string' ? parseFloat(bytes) : bytes;
    if (bytesNum < 1024) return `${bytesNum} B`;
    if (bytesNum < 1024 * 1024) return `${(bytesNum / 1024).toFixed(1)} KB`;
    return `${(bytesNum / 1024 / 1024).toFixed(2)} MB`;
  };

  if (uploadedFiles.length === 0) {
    return (
      <div
        className={`p-6 rounded-xl text-center ${
          isDragging 
            ? 'border-2 border-indigo-500 bg-indigo-500/10' 
            : theme === 'dark' ? 'bg-slate-900/50 border border-slate-800' : 'bg-gray-50 border border-gray-200'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          multiple
          accept=".js,.jsx,.ts,.tsx,.py,.java,.c,.cpp,.go,.rs,.html,.css,.json,.md,.txt,.sh,.php,.rb,.swift,.kt"
          onChange={(e) => handleFileSelect(e.target.files)}
        />
        
        <div className="text-4xl mb-3">📁</div>
        <p className={`font-medium mb-1 ${theme === 'dark' ? 'text-slate-200' : 'text-gray-700'}`}>
          Drag code files here or click to upload
        </p>
        <p className={`text-sm ${theme === 'dark' ? 'text-slate-400' : 'text-gray-500'}`}>
          Up to 10 files will be analyzed together (max 5MB each)
        </p>
        
        <button
          onClick={() => fileInputRef.current?.click()}
          className={`mt-4 px-4 py-2 rounded-lg transition-colors ${
            isDragging 
              ? 'bg-indigo-600 hover:bg-indigo-700' 
              : theme === 'dark' 
                ? 'bg-indigo-600/20 hover:bg-indigo-600/30' 
                : 'bg-gray-200 hover:bg-gray-300'
          } text-white`}
        >
          Browse Files
        </button>
      </div>
    );
  }

  return (
    <div className={`rounded-xl ${theme === 'dark' ? 'bg-slate-900 border-slate-800' : 'bg-gray-50 border-gray-200'} border`}>
      {/* Header */}
      <div className={`p-3 border-b ${theme === 'dark' ? 'border-slate-800' : 'border-gray-200'} flex items-center justify-between`}>
        <span className={`text-sm font-medium ${theme === 'dark' ? 'text-slate-200' : 'text-gray-700'}`}>
          {selectedFiles.size} of {uploadedFiles.length} files selected for context
        </span>
        <button
          onClick={clearAllFiles}
          className={`text-xs ${theme === 'dark' ? 'text-slate-400 hover:text-red-400' : 'text-gray-500 hover:text-red-500'}`}
        >
          Clear all
        </button>
      </div>

      {/* File list */}
      <div className="max-h-48 overflow-y-auto">
        {uploadedFiles.map((file) => (
          <label
            key={file.id}
            className={`flex items-center gap-3 p-3 cursor-pointer transition-colors ${
              selectedFiles.has(file.id)
                ? theme === 'dark' 
                  ? 'bg-indigo-600/20 border-l-2 border-indigo-500' 
                  : 'bg-indigo-50 border-l-2 border-indigo-500'
                : theme === 'dark' 
                  ? 'hover:bg-slate-800/50' 
                  : 'hover:bg-gray-100'
            }`}
          >
            <input
              type="checkbox"
              checked={selectedFiles.has(file.id)}
              onChange={() => toggleFileSelection(file.id)}
              className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-indigo-500"
            />
            
            <span className="text-xl">{getFileIcon(file.filename)}</span>
            
            <div className="flex-1 min-w-0">
              <div className={`truncate text-sm ${theme === 'dark' ? 'text-slate-200' : 'text-gray-700'}`}>
                {file.filename}
              </div>
              <div className={`text-xs ${theme === 'dark' ? 'text-slate-500' : 'text-gray-400'}`}>
                {formatSize(file.size)}
              </div>
            </div>
          </label>
        ))}
      </div>

      {/* Add more button */}
      {uploadedFiles.length < 10 && (
        <button
          onClick={() => fileInputRef.current?.click()}
          className={`w-full p-3 text-sm border-t ${theme === 'dark' ? 'border-slate-800 hover:bg-slate-800/50' : 'border-gray-200 hover:bg-gray-100'} transition-colors`}
        >
          + Add more files
        </button>
      )}
    </div>
  );
}
