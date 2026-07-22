import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useSession } from '../state/SessionContext'
import { useToast } from '../state/ToastContext'

const TYPE_STYLES = {
  Epic: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  Story: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  Bug: 'bg-red-500/15 text-red-300 border-red-500/30',
  Task: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
}

function QuestionGroup({ group }) {
  const { submitClarification } = useSession()
  const toast = useToast()
  const [answers, setAnswers] = useState({})
  const [busy, setBusy] = useState(false)

  const questions = group.questions || []

  async function run(skip) {
    setBusy(true)
    try {
      const payload = skip ? {} : Object.fromEntries(questions.map((q) => [q.id, (answers[q.id] || '').trim()]))
      await submitClarification(group.group_id, payload, skip)
    } catch (err) {
      // 409 = the draft already moved on (answered elsewhere or timed out) — the form will clear on refresh.
      if (err.status !== 409) toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  const answeredCount = questions.filter((q) => (answers[q.id] || '').trim()).length

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] p-3 space-y-2.5"
    >
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-[var(--bg-hover)] text-[var(--text-tertiary)] shrink-0">
          Item {group.item_index + 1}
        </span>
        <span
          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${
            TYPE_STYLES[group.issue_type] || TYPE_STYLES.Story
          }`}
        >
          {group.issue_type}
        </span>
        <span className="flex-1 min-w-0 truncate text-xs font-medium text-[var(--text-primary)]">
          {group.item_title}
        </span>
      </div>

      <div className="space-y-2.5">
        {questions.map((q) => (
          <div key={q.id} className="space-y-1">
            <label className="block text-xs font-medium text-[var(--text-primary)]">{q.question}</label>
            {q.reason && <div className="text-[10px] text-[var(--text-tertiary)]">{q.reason}</div>}
            <textarea
              value={answers[q.id] || ''}
              onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
              disabled={busy}
              rows={1}
              placeholder="Your answer (optional)…"
              className="w-full resize-none rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs outline-none focus:border-[var(--accent)] disabled:opacity-50 max-h-24"
            />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => run(false)}
          disabled={busy || answeredCount === 0}
          className="text-xs px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium transition-colors"
        >
          {busy ? '…' : `Submit ${answeredCount || ''}`.trim()}
        </button>
        <button
          onClick={() => run(true)}
          disabled={busy}
          title="Draft this item now with best-guess assumptions instead of answering"
          className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors disabled:opacity-40"
        >
          Skip
        </button>
      </div>
    </motion.div>
  )
}

export default function ClarifyingQuestions() {
  const { session, submitClarification } = useSession()
  const toast = useToast()
  const [skippingAll, setSkippingAll] = useState(false)
  const groups = session?.pending_questions || []

  if (groups.length === 0) return null

  async function skipAll() {
    setSkippingAll(true)
    try {
      // Snapshot the ids first — the list mutates as each skip resolves and the session refreshes.
      const ids = groups.map((g) => g.group_id)
      for (const id of ids) {
        await submitClarification(id, {}, true).catch((err) => {
          if (err.status !== 409) throw err
        })
      }
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSkippingAll(false)
    }
  }

  return (
    <div className="rounded-xl border border-[var(--accent)]/40 bg-[var(--accent)]/5 p-3 space-y-2.5">
      <div className="flex items-center gap-2">
        <span className="w-5 h-5 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-[var(--text-primary)]">
            A few details would help me avoid guessing
          </div>
          <div className="text-[10px] text-[var(--text-tertiary)]">
            {groups.length} item{groups.length === 1 ? '' : 's'} drafting are waiting — answer what you can, skip
            the rest. Unanswered items get a best-guess draft with the assumption noted.
          </div>
        </div>
        {groups.length > 1 && (
          <button
            onClick={skipAll}
            disabled={skippingAll}
            className="text-[10px] px-2 py-1 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors disabled:opacity-40 shrink-0"
          >
            {skippingAll ? '…' : 'Skip all'}
          </button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {groups.map((g) => (
          <QuestionGroup key={g.group_id} group={g} />
        ))}
      </AnimatePresence>
    </div>
  )
}
