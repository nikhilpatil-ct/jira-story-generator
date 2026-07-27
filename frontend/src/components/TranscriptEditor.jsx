import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useSession } from '../state/SessionContext'

const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.docx', '.pdf']

// The source toggle: "Auto" lets the backend detect transcript-vs-document; the other two force a path.
// "transcript" -> speech cleanup + infer story boundaries; "document" -> whitespace-only cleanup +
// preserve the doc's own itemization (the right choice for a BRD/PRD/spec).
const SOURCE_OPTIONS = [
  { value: 'auto', label: 'Auto', hint: 'Detect transcript vs. BRD/spec automatically' },
  { value: 'transcript', label: 'Transcript', hint: 'Spoken meeting transcript — apply speech cleanup' },
  { value: 'document', label: 'BRD / Spec', hint: 'Structured document — preserve its own itemization' },
]

// What the source area calls the input for each toggle value. "Auto" hasn't committed to a path, so it
// names both; picking Transcript or BRD/Spec narrows the label to just that one.
const SOURCE_LABELS = {
  auto: 'Transcript / BRD',
  transcript: 'Transcript',
  document: 'BRD / Spec',
}

// Same idea, phrased to read inside the upload prompt ("Drag & drop a ___ file…").
const SOURCE_DROP_LABELS = {
  auto: 'transcript or BRD',
  transcript: 'transcript',
  document: 'BRD / spec',
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function TranscriptEditor() {
  const { session, sendMessage, sending, stopping, stopGeneration, currentStepLabel } = useSession()
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [sourceType, setSourceType] = useState('auto')
  const fileInputRef = useRef(null)
  const loadedSessionId = useRef(null)

  useEffect(() => {
    if (!session || loadedSessionId.current === session.id) return
    loadedSessionId.current = session.id
    setText(session.transcript || '')
    setFile(null)
    setUploadError(null)
    // Restore this session's last source choice (defaults to Auto for a fresh/never-set session).
    setSourceType(localStorage.getItem(`source_type:${session.id}`) || 'auto')
  }, [session])

  useEffect(() => {
    if (session) localStorage.setItem(`source_type:${session.id}`, sourceType)
  }, [sourceType, session])

  async function handleFiles(files) {
    const picked = files?.[0]
    if (!picked) return
    const ext = '.' + picked.name.split('.').pop().toLowerCase()
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setUploadError(`Unsupported file type: ${ext}. Use .txt, .docx, or .pdf.`)
      return
    }
    setUploading(true)
    setUploadError(null)
    try {
      const { text: extracted } = await api.uploadFile(picked)
      setText(extracted)
      setFile({ name: picked.name, size: picked.size })
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setUploading(false)
    }
  }

  function handleRemove() {
    setFile(null)
    setText('')
    setUploadError(null)
  }

  const hasStories = (session?.stories?.length ?? 0) > 0

  async function handleGenerate() {
    if (!text.trim() || hasStories) return
    await sendMessage(text, sourceType === 'auto' ? null : sourceType)
  }

  const hasTranscript = text.trim().length > 0

  return (
    <div
      className="shrink-0 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-subtle)] overflow-hidden relative"
      onDragOver={(e) => {
        e.preventDefault()
        setDragActive(true)
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragActive(false)
        handleFiles(e.dataTransfer.files)
      }}
    >
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-[var(--border-subtle)]">
        <div className="text-sm font-medium text-[var(--text-secondary)] shrink-0">{SOURCE_LABELS[sourceType]}</div>
        <div className="flex items-center gap-2 min-w-0">
          <div
            role="radiogroup"
            aria-label="Source type"
            className="flex items-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] p-0.5"
          >
            {SOURCE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                role="radio"
                aria-checked={sourceType === opt.value}
                title={opt.hint}
                onClick={() => setSourceType(opt.value)}
                disabled={sending}
                className={`text-xs px-2.5 py-1 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  sourceType === opt.value
                    ? 'bg-[var(--accent)] text-white'
                    : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {sending ? (
            <button
              onClick={stopGeneration}
              disabled={stopping}
              title="Stop the current generation run"
              className="text-xs px-3 py-1.5 rounded-lg bg-[var(--danger)] hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium transition-colors shrink-0 flex items-center gap-1.5"
            >
              <span className="inline-block h-2 w-2 rounded-[2px] bg-white/90 shrink-0" />
              {stopping ? 'Stopping…' : `Stop · ${currentStepLabel}`}
            </button>
          ) : (
            <button
              onClick={handleGenerate}
              disabled={!hasTranscript || hasStories}
              title={hasStories ? 'Items already generated — start a new session, or use the chat to revise or regenerate' : undefined}
              className="text-xs px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors shrink-0"
            >
              {hasStories ? 'Items Generated' : 'Generate Items'}
            </button>
          )}
        </div>
      </div>

      <div className="p-5">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />

        {!hasTranscript ? (
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-[var(--border-strong)] hover:border-[var(--accent)] hover:bg-[var(--bg-hover)] py-8 transition-colors disabled:opacity-50"
          >
            <span className="text-2xl">⇧</span>
            <span className="text-sm font-medium text-[var(--text-secondary)]">
              {uploading ? 'Uploading…' : `Drag & drop a ${SOURCE_DROP_LABELS[sourceType]} file, or click to upload`}
            </span>
            <span className="text-xs text-[var(--text-tertiary)]">.txt, .md, .docx, or .pdf</span>
          </button>
        ) : (
          <div className="flex items-center gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-app)] px-4 py-3">
            <span className="text-xl shrink-0">📄</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{file?.name || 'Transcript loaded'}</div>
              <div className="text-xs text-[var(--text-tertiary)]">
                {file ? `${formatSize(file.size)} · ` : ''}
                {text.length.toLocaleString()} characters ready to process
              </div>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-xs px-2.5 py-1 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors shrink-0"
              disabled={uploading}
            >
              Replace
            </button>
            <button
              onClick={handleRemove}
              className="text-xs px-2 py-1 rounded-lg hover:bg-[var(--bg-hover)] text-[var(--text-tertiary)] hover:text-[var(--danger)] transition-colors shrink-0"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {uploadError && (
        <div className="px-4 pb-3 text-xs text-[var(--danger)]">{uploadError}</div>
      )}

      {dragActive && (
        <div className="absolute inset-0 bg-[var(--accent)]/10 border-2 border-dashed border-[var(--accent)] rounded-xl flex items-center justify-center pointer-events-none">
          <div className="text-sm font-medium text-[var(--accent-strong)]">Drop file to upload</div>
        </div>
      )}
    </div>
  )
}
