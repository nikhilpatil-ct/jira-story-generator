import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useSession } from '../state/SessionContext'

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function SessionRow({ s, active, onSelect, onRename, onToggleFavorite, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(s.title)

  function commitRename() {
    setEditing(false)
    if (title.trim() && title !== s.title) onRename(s.id, title.trim())
    else setTitle(s.title)
  }

  return (
    <div
      onClick={() => !editing && onSelect(s.id)}
      className={`group flex items-center gap-2 rounded-lg px-2.5 py-2 cursor-pointer text-sm transition-colors ${
        active ? 'bg-[var(--bg-hover)] text-[var(--text-primary)]' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'
      }`}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitRename()
              if (e.key === 'Escape') {
                setTitle(s.title)
                setEditing(false)
              }
            }}
            onClick={(e) => e.stopPropagation()}
            className="w-full bg-transparent border-b border-[var(--border-strong)] outline-none text-sm"
          />
        ) : (
          <>
            <div className="truncate font-medium">{s.title}</div>
            <div className="text-xs text-[var(--text-tertiary)] truncate">
              {s.story_count} item{s.story_count === 1 ? '' : 's'} · {timeAgo(s.updated_at)}
            </div>
          </>
        )}
      </div>
      {!editing && (
        <div className="hidden group-hover:flex items-center gap-1 shrink-0">
          <button
            title={s.favorite ? 'Unfavorite' : 'Favorite'}
            onClick={(e) => {
              e.stopPropagation()
              onToggleFavorite(s.id, !s.favorite)
            }}
            className={`text-xs px-1 ${s.favorite ? 'text-[var(--warning)]' : 'text-[var(--text-tertiary)] hover:text-[var(--text-primary)]'}`}
          >
            ★
          </button>
          <button
            title="Rename"
            onClick={(e) => {
              e.stopPropagation()
              setEditing(true)
            }}
            className="text-xs px-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
          >
            ✎
          </button>
          <button
            title="Delete"
            onClick={(e) => {
              e.stopPropagation()
              if (confirm(`Delete "${s.title}"?`)) onDelete(s.id)
            }}
            className="text-xs px-1 text-[var(--text-tertiary)] hover:text-[var(--danger)]"
          >
            ✕
          </button>
        </div>
      )}
      {!editing && s.favorite && <span className="group-hover:hidden text-[var(--warning)] text-xs">★</span>}
    </div>
  )
}

export default function Sidebar({ collapsed, onToggleCollapsed }) {
  const { sessions, activeSessionId, selectSession, newSession, renameSession, toggleFavorite, deleteSession } =
    useSession()
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return sessions
    return sessions.filter((s) => s.title.toLowerCase().includes(q))
  }, [sessions, query])

  const favorites = filtered.filter((s) => s.favorite)
  const others = filtered.filter((s) => !s.favorite)

  if (collapsed) {
    return (
      <div className="w-14 shrink-0 border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col items-center py-3 gap-3">
        <button
          onClick={onToggleCollapsed}
          className="w-9 h-9 rounded-lg hover:bg-[var(--bg-hover)] flex items-center justify-center text-[var(--text-secondary)]"
          title="Expand sidebar"
        >
          »
        </button>
        <button
          onClick={() => newSession()}
          className="w-9 h-9 rounded-lg bg-[var(--accent)] text-white flex items-center justify-center"
          title="New session"
        >
          +
        </button>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 272, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      className="w-68 shrink-0 border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col overflow-hidden"
      style={{ width: 272 }}
    >
      <div className="p-3 flex items-center gap-2">
        <button
          onClick={() => newSession()}
          className="flex-1 flex items-center gap-2 justify-center rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] text-white text-sm font-medium py-2 transition-colors"
        >
          + New session
        </button>
        <button
          onClick={onToggleCollapsed}
          className="w-9 h-9 rounded-lg hover:bg-[var(--bg-hover)] flex items-center justify-center text-[var(--text-secondary)] shrink-0"
          title="Collapse sidebar"
        >
          «
        </button>
      </div>

      <div className="px-3 pb-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search sessions..."
          className="w-full rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] px-3 py-1.5 text-sm outline-none focus:border-[var(--accent)] transition-colors"
        />
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-3">
        {favorites.length > 0 && (
          <div>
            <div className="px-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
              Favorites
            </div>
            <div className="space-y-0.5">
              <AnimatePresence initial={false}>
                {favorites.map((s) => (
                  <SessionRow
                    key={s.id}
                    s={s}
                    active={s.id === activeSessionId}
                    onSelect={selectSession}
                    onRename={renameSession}
                    onToggleFavorite={toggleFavorite}
                    onDelete={deleteSession}
                  />
                ))}
              </AnimatePresence>
            </div>
          </div>
        )}
        <div>
          {favorites.length > 0 && (
            <div className="px-2 text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)] mb-1">
              All sessions
            </div>
          )}
          <div className="space-y-0.5">
            {others.map((s) => (
              <SessionRow
                key={s.id}
                s={s}
                active={s.id === activeSessionId}
                onSelect={selectSession}
                onRename={renameSession}
                onToggleFavorite={toggleFavorite}
                onDelete={deleteSession}
              />
            ))}
            {filtered.length === 0 && (
              <div className="text-xs text-[var(--text-tertiary)] px-2 py-4 text-center">No sessions found</div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}
