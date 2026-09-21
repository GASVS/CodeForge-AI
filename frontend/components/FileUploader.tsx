import { useRef } from 'react'
import { Upload, X } from 'lucide-react'

interface Props {
  onFileSelect: (files: File[]) => void
  uploadedCount: number
}

export default function FileUploader({ onFileSelect, uploadedCount }: Props) {
  const ref = useRef<HTMLInputElement>(null)

  return (
    <div className="flex items-center gap-4 p-2 border rounded-lg border-indigo-600/20" style={{ color: 'var(--foreground)' }}>
      <button type="button" onClick={() => ref.current?.click()} className="p-2 rounded bg-indigo-600 hover:bg-indigo-700 text-white">
        <Upload size={20} />
      </button>
      <span>{uploadedCount} file{uploadedCount === 1 ? '' : 's'} uploaded</span>
      <input type="file" ref={ref} multiple className="hidden" onChange={e => e.target.files && onFileSelect(Array.from(e.target.files))} />
      <button type="button" onClick={()=>{onFileSelect([])}} className="p-2 rounded bg-red-600 hover:bg-red-700 text-white">
        <X size={18} />
      </button>
    </div>
  )
}
