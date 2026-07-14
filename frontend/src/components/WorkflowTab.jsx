import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { useSession } from '../state/SessionContext'

const STEPS = [
  {
    key: 'cleaning',
    label: 'Clean transcript',
    detail: 'Strip filler words, timestamps, and ASR noise',
    logStages: ['cleaning'],
  },
  {
    key: 'extracting',
    label: 'Extract requirements',
    detail: 'Identify stories, epics, bugs, risks, and action items',
    logStages: ['extracting'],
  },
  {
    key: 'drafting',
    label: 'Draft items',
    detail: 'Write each JIRA item with type-specific fields',
    logStages: ['drafting'],
  },
  {
    key: 'validating',
    label: 'Validate & refine',
    detail: 'Score against quality bar, refine if below threshold',
    logStages: ['validating'],
  },
  {
    key: 'done',
    label: 'Done',
    detail: 'Items ready for review',
    logStages: ['pipeline'],
  },
  {
    key: 'jira',
    label: 'Create in JIRA',
    detail: 'Push generated items to your JIRA project',
    logStages: ['jira'],
  },
]

function StatusIcon({ status }) {
  if (status === 'done') {
    return (
      <div className="w-6 h-6 rounded-full bg-[var(--success)] flex items-center justify-center text-white text-xs shrink-0">
        ✓
      </div>
    )
  }
  if (status === 'active') {
    return (
      <div className="w-6 h-6 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin shrink-0" />
    )
  }
  if (status === 'error') {
    return (
      <div className="w-6 h-6 rounded-full bg-[var(--danger)] flex items-center justify-center text-white text-xs shrink-0">
        ✕
      </div>
    )
  }
  return <div className="w-6 h-6 rounded-full border-2 border-[var(--border-strong)] shrink-0" />
}

function SubProcessLines({ lines }) {
  if (lines.length === 0) {
    return <div className="text-xs text-[var(--text-tertiary)] italic py-1.5">No activity logged for this step yet.</div>
  }
  return (
    <div className="rounded-lg bg-[var(--bg-app)] border border-[var(--border-subtle)] divide-y divide-[var(--border-subtle)] overflow-hidden">
      {lines.map((l, i) => (
        <div key={i} className="flex gap-2 px-2.5 py-1.5 text-xs">
          <span className="text-[var(--text-tertiary)] shrink-0 font-mono">
            {new Date(l.ts).toLocaleTimeString([], { hour12: false })}
          </span>
          <span className={`flex-1 ${l.message.startsWith('FAILED') ? 'text-[var(--danger)]' : 'text-[var(--text-secondary)]'}`}>
            {l.message}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function WorkflowTab() {
  const { session, sending, currentStep } = useSession()
  const [expanded, setExpanded] = useState(() => new Set())

  const logs = session?.logs || []
  const activeIndex = STEPS.findIndex((s) => s.key === currentStep)

  useEffect(() => {
    if (sending && currentStep) {
      setExpanded((prev) => new Set(prev).add(currentStep))
    }
  }, [sending, currentStep])

  function toggle(key) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const hasRun = sending || (session?.stories?.length ?? 0) > 0

  if (!hasRun) {
    return (
      <div className="text-sm text-[var(--text-tertiary)] text-center py-8">
        No workflow run yet — upload a transcript and click "Generate Items" to start.
      </div>
    )
  }

  const visibleSteps = STEPS.filter((s) => s.key !== 'jira' || logs.some((l) => l.stage === 'jira'))

  return (
    <div className="space-y-0.5">
      <div className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)] mb-3">
        {sending ? 'Run in progress' : 'Last run'}
      </div>
      {visibleSteps.map((step, i) => {
        let status
        if (sending) {
          status = i < activeIndex || currentStep === 'done' ? 'done' : i === activeIndex ? 'active' : 'pending'
        } else {
          status = 'done'
        }
        const lines = logs.filter((l) => step.logStages.includes(l.stage))
        // current_step never reaches a dedicated "jira" value on the backend, so infer status for
        // this step from whether any create/failure lines have landed yet instead.
        if (step.key === 'jira' && sending) {
          status = lines.length > 0 ? 'active' : 'pending'
        }
        const isLast = i === visibleSteps.length - 1
        const isOpen = expanded.has(step.key)

        return (
          <div key={step.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <StatusIcon status={status} />
              {!isLast && (
                <div
                  className={`w-0.5 flex-1 min-h-[1.25rem] ${
                    status === 'done' ? 'bg-[var(--success)]' : 'bg-[var(--border-subtle)]'
                  }`}
                />
              )}
            </div>
            <motion.div
              initial={{ opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              className="pb-4 flex-1 min-w-0"
            >
              <button
                onClick={() => toggle(step.key)}
                className="w-full flex items-center gap-2 text-left group"
              >
                <div className="flex-1 min-w-0">
                  <div
                    className={`text-sm font-medium ${
                      status === 'pending' ? 'text-[var(--text-tertiary)]' : 'text-[var(--text-primary)]'
                    }`}
                  >
                    {step.label}
                  </div>
                  <div className="text-xs text-[var(--text-tertiary)] mt-0.5">{step.detail}</div>
                </div>
                {lines.length > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--bg-hover)] text-[var(--text-tertiary)] shrink-0">
                    {lines.length}
                  </span>
                )}
                <span className="text-[var(--text-tertiary)] shrink-0 group-hover:text-[var(--text-secondary)]">
                  {isOpen ? '▾' : '▸'}
                </span>
              </button>

              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="pt-2">
                      <SubProcessLines lines={lines} />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          </div>
        )
      })}
    </div>
  )
}
