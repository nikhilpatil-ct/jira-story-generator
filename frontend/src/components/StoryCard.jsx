import { useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api'
import { useSession } from '../state/SessionContext'
import { useToast } from '../state/ToastContext'

const TYPE_STYLES = {
  Epic: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  Story: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  Bug: 'bg-red-500/15 text-red-300 border-red-500/30',
}

const PRIORITY_STYLES = {
  Highest: 'text-red-400',
  High: 'text-orange-400',
  Medium: 'text-yellow-400',
  Low: 'text-blue-400',
  Lowest: 'text-[var(--text-tertiary)]',
}

function ScoreBadge({ score, valid }) {
  const color = valid ? 'text-[var(--success)]' : score >= 50 ? 'text-[var(--warning)]' : 'text-[var(--danger)]'
  return <span className={`text-xs font-semibold ${color}`}>{score}/100</span>
}

function ActionButton({ label, onClick, busy, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className="text-xs px-2.5 py-1 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors disabled:opacity-40"
    >
      {busy ? '…' : label}
    </button>
  )
}

function Body({ story }) {
  if (story.issue_type === 'Epic') {
    return (
      <div className="space-y-2 text-sm text-[var(--text-secondary)]">
        <p>
          <span className="font-medium text-[var(--text-primary)]">Goal: </span>
          {story.goal}
        </p>
        <p>
          <span className="font-medium text-[var(--text-primary)]">Business value: </span>
          {story.business_value}
        </p>
        {story.success_criteria?.length > 0 && (
          <div>
            <div className="font-medium text-[var(--text-primary)] mb-1">Success criteria</div>
            <ul className="list-disc list-inside space-y-0.5">
              {story.success_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }
  if (story.issue_type === 'Bug') {
    return (
      <div className="space-y-2 text-sm text-[var(--text-secondary)]">
        {story.steps_to_reproduce?.length > 0 && (
          <div>
            <div className="font-medium text-[var(--text-primary)] mb-1">Steps to reproduce</div>
            <ol className="list-decimal list-inside space-y-0.5">
              {story.steps_to_reproduce.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </div>
        )}
        <p>
          <span className="font-medium text-[var(--text-primary)]">Expected: </span>
          {story.expected_result}
        </p>
        <p>
          <span className="font-medium text-[var(--text-primary)]">Actual: </span>
          {story.actual_result}
        </p>
        <p>
          <span className="font-medium text-[var(--text-primary)]">Severity: </span>
          {story.severity}
        </p>
        {story.environment && (
          <p>
            <span className="font-medium text-[var(--text-primary)]">Environment: </span>
            {story.environment}
          </p>
        )}
        {story.root_cause && (
          <p>
            <span className="font-medium text-[var(--text-primary)]">Root cause: </span>
            {story.root_cause}
          </p>
        )}
      </div>
    )
  }
  return (
    <div className="space-y-2 text-sm text-[var(--text-secondary)]">
      <p className="italic">{story.user_story}</p>
      {story.acceptance_criteria?.length > 0 && (
        <div>
          <div className="font-medium text-[var(--text-primary)] mb-1">Acceptance criteria</div>
          <ul className="list-disc list-inside space-y-0.5">
            {story.acceptance_criteria.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {story.story_points != null && (
        <p>
          <span className="font-medium text-[var(--text-primary)]">Story points: </span>
          {story.story_points}
        </p>
      )}
    </div>
  )
}

export default function StoryCard({ gs, index, jiraResult, jiraConfigured }) {
  const { runStoryAction, activeSessionId, refreshActiveSession } = useSession()
  const toast = useToast()
  const [expanded, setExpanded] = useState(false)
  const [busyAction, setBusyAction] = useState(null)
  const [preview, setPreview] = useState(null)
  const [creating, setCreating] = useState(false)
  const [localJiraResult, setLocalJiraResult] = useState(jiraResult)
  const [customPrompt, setCustomPrompt] = useState('')

  const story = gs.story

  async function runAction(action, instructions) {
    setBusyAction(action)
    try {
      await runStoryAction(index, action, instructions)
      if (action === 'custom') setCustomPrompt('')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusyAction(null)
    }
  }

  function applyCustomPrompt() {
    const trimmed = customPrompt.trim()
    if (trimmed && busyAction !== 'custom') runAction('custom', trimmed)
  }

  async function handlePreview() {
    // Toggle: a second click hides the payload; opening always fetches a fresh copy of the current story.
    if (preview) {
      setPreview(null)
      return
    }
    try {
      const fields = await api.jiraPreview(activeSessionId, index)
      setPreview(fields)
    } catch (err) {
      toast.error(err.message)
    }
  }

  async function handleCreate() {
    setCreating(true)
    try {
      const result = await api.jiraRetry(activeSessionId, index)
      setLocalJiraResult(result)
      await refreshActiveSession()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden"
    >
      <div role="button" tabIndex={0} onClick={() => setExpanded((e) => !e)} className="w-full flex items-center gap-2 px-4 py-3 text-left cursor-pointer">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border shrink-0 ${TYPE_STYLES[story.issue_type]}`}>
          {story.issue_type}
        </span>
        <span className="flex-1 min-w-0 truncate text-sm font-medium">{story.summary}</span>
        <span className={`text-xs font-medium shrink-0 ${PRIORITY_STYLES[story.priority]}`}>{story.priority}</span>
        <ScoreBadge score={gs.validation.score} valid={gs.validation.is_valid} />

        {localJiraResult?.key ? (
          <span className="flex items-center gap-1.5 shrink-0">
            <a
              href={localJiraResult.url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-xs font-medium text-[var(--success)] hover:underline"
            >
              {localJiraResult.key} ✓
            </a>
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleCreate()
              }}
              disabled={!jiraConfigured || creating}
              title="Push your latest edits to this same JIRA ticket"
              className="text-xs px-2 py-1 rounded-lg border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {creating ? '…' : 'Update'}
            </button>
          </span>
        ) : (
          <span className="flex items-center gap-1.5 shrink-0">
            {localJiraResult?.held_for_review && (
              <span
                title={localJiraResult.reason}
                className="text-[10px] font-semibold px-2 py-0.5 rounded-full border border-[var(--warning)]/40 bg-[var(--warning)]/15 text-[var(--warning)] cursor-help"
              >
                Needs review
              </span>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleCreate()
              }}
              disabled={!jiraConfigured || creating}
              title={jiraConfigured ? 'Create this item in JIRA' : 'JIRA not configured'}
              className={`text-xs px-2.5 py-1 rounded-lg font-medium shrink-0 transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                localJiraResult?.error
                  ? 'bg-[var(--danger)]/15 text-[var(--danger)] hover:bg-[var(--danger)]/25'
                  : 'bg-[var(--accent)] text-white hover:bg-[var(--accent-strong)]'
              }`}
            >
              {creating ? '…' : localJiraResult?.error ? 'Retry' : 'Create'}
            </button>
          </span>
        )}

        <span className="text-[var(--text-tertiary)] shrink-0">{expanded ? '▾' : '▸'}</span>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-[var(--border-subtle)] pt-3">
          {story.description && <p className="text-sm text-[var(--text-secondary)]">{story.description}</p>}
          <Body story={story} />

          {story.labels?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {story.labels.map((l) => (
                <span key={l} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-hover)] text-[var(--text-tertiary)]">
                  {l}
                </span>
              ))}
            </div>
          )}

          {gs.validation.issues?.length > 0 && (
            <div className="rounded-lg bg-[var(--warning)]/10 border border-[var(--warning)]/30 p-2.5 space-y-1">
              {gs.validation.issues.map((iss, i) => (
                <div key={i} className="text-xs text-[var(--text-secondary)]">
                  <span className="font-medium text-[var(--warning)]">[{iss.field}]</span> {iss.problem}
                </div>
              ))}
            </div>
          )}

          {gs.test_cases?.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-medium text-[var(--text-primary)]">Test cases</div>
              {gs.test_cases.map((tc, i) => (
                <div key={i} className="text-xs text-[var(--text-secondary)] rounded-lg bg-[var(--bg-app)] p-2">
                  <div className="font-medium text-[var(--text-primary)]">{tc.title}</div>
                  <ol className="list-decimal list-inside">
                    {tc.steps.map((s, j) => (
                      <li key={j}>{s}</li>
                    ))}
                  </ol>
                  <div className="mt-1">
                    <span className="font-medium">Expected: </span>
                    {tc.expected_result}
                  </div>
                </div>
              ))}
            </div>
          )}

          {gs.risks?.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-medium text-[var(--text-primary)]">Risks</div>
              {gs.risks.map((r, i) => (
                <div key={i} className="text-xs text-[var(--text-secondary)] rounded-lg bg-[var(--bg-app)] p-2">
                  <div className="font-medium text-[var(--danger)]">{r.risk}</div>
                  <div>
                    <span className="font-medium">Impact: </span>
                    {r.impact}
                  </div>
                  <div>
                    <span className="font-medium">Mitigation: </span>
                    {r.mitigation}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-1.5 pt-1">
            <ActionButton label="Improve wording" onClick={() => runAction('improve_wording')} busy={busyAction === 'improve_wording'} />
            <ActionButton label="Expand AC" onClick={() => runAction('expand_ac')} busy={busyAction === 'expand_ac'} />
            <ActionButton label="Test cases" onClick={() => runAction('generate_test_cases')} busy={busyAction === 'generate_test_cases'} />
            <ActionButton label="Risk analysis" onClick={() => runAction('risk_analysis')} busy={busyAction === 'risk_analysis'} />
            <ActionButton label="Regenerate" onClick={() => runAction('regenerate')} busy={busyAction === 'regenerate'} />
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              applyCustomPrompt()
            }}
            className="flex items-center gap-1.5 pt-1"
          >
            <input
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              disabled={busyAction === 'custom'}
              placeholder='Or tell me exactly what to change (e.g. "add an AC for rate limiting")'
              className="flex-1 min-w-0 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2.5 py-1.5 text-xs outline-none focus:border-[var(--accent)] disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={busyAction === 'custom' || !customPrompt.trim()}
              className="text-xs px-3 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium transition-colors shrink-0"
            >
              {busyAction === 'custom' ? '…' : 'Apply'}
            </button>
          </form>

          <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-[var(--border-subtle)] mt-1">
            <ActionButton
              label={preview ? 'Hide JIRA payload' : 'Preview JIRA payload'}
              onClick={handlePreview}
              disabled={!jiraConfigured}
            />
            {!jiraConfigured && <span className="text-[10px] text-[var(--text-tertiary)]">JIRA not configured</span>}
            {localJiraResult?.error && <span className="text-xs text-[var(--danger)]">{localJiraResult.error}</span>}
            {localJiraResult?.held_for_review && (
              <span className="text-xs text-[var(--warning)]">{localJiraResult.reason}</span>
            )}
          </div>

          {preview && (
            <div className="rounded-lg bg-[var(--bg-app)] overflow-hidden">
              <div className="flex items-center justify-between px-2 py-1 border-b border-[var(--border-subtle)]">
                <span className="text-[10px] font-medium text-[var(--text-tertiary)]">JIRA payload</span>
                <button
                  onClick={() => setPreview(null)}
                  className="text-[10px] px-1.5 py-0.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors"
                >
                  Hide
                </button>
              </div>
              <pre className="text-[10px] p-2 overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(preview, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}
