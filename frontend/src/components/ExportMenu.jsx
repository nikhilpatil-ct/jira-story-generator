import { useState } from 'react'
import { api } from '../api'
import { useSession } from '../state/SessionContext'

const FORMATS = [
  { key: 'json', label: 'JSON' },
  { key: 'csv', label: 'CSV' },
  { key: 'markdown', label: 'Markdown' },
]

export default function ExportMenu() {
  const { activeSessionId, session } = useSession()
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  async function copyToClipboard() {
    await navigator.clipboard.writeText(JSON.stringify(session?.stories || [], null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs px-2.5 py-1.5 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors"
      >
        Export ▾
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-40 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface-raised)] shadow-lg z-10 overflow-hidden">
          {FORMATS.map((f) => (
            <a
              key={f.key}
              href={api.exportUrl(activeSessionId, f.key)}
              download
              onClick={() => setOpen(false)}
              className="block px-3 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
            >
              Export as {f.label}
            </a>
          ))}
          <button
            onClick={copyToClipboard}
            className="w-full text-left px-3 py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] border-t border-[var(--border-subtle)]"
          >
            {copied ? 'Copied!' : 'Copy JSON to clipboard'}
          </button>
        </div>
      )}
    </div>
  )
}
