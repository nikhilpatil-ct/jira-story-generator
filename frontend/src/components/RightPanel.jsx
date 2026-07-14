import { useEffect, useRef, useState } from 'react'
import { useSession } from '../state/SessionContext'
import ExportMenu from './ExportMenu'
import StoryCard from './StoryCard'
import WorkflowTab from './WorkflowTab'

const TABS = ['Workflow', 'Summary', 'Jira Items', 'Logs']

function jiraResultFor(session, id) {
  return session?.jira_results?.find((r) => r.id === id)
}

function SummaryTab({ session }) {
  if (!session) return null
  const counts = session.stories.reduce((acc, gs) => {
    acc[gs.story.issue_type] = (acc[gs.story.issue_type] || 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-4">
      {session.summary && (
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{session.summary}</p>
      )}

      {session.stories.length > 0 && (
        <div className="flex gap-2">
          {Object.entries(counts).map(([type, count]) => (
            <div key={type} className="flex-1 rounded-lg border border-[var(--border-subtle)] p-3 text-center">
              <div className="text-lg font-semibold">{count}</div>
              <div className="text-xs text-[var(--text-tertiary)]">{type}{count === 1 ? '' : 's'}</div>
            </div>
          ))}
        </div>
      )}

      {session.risks?.length > 0 && (
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)] mb-1.5">Risks</div>
          <ul className="space-y-1 text-sm text-[var(--text-secondary)] list-disc list-inside">
            {session.risks.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {session.action_items?.length > 0 && (
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)] mb-1.5">
            Action items
          </div>
          <ul className="space-y-1 text-sm text-[var(--text-secondary)] list-disc list-inside">
            {session.action_items.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {session.open_questions?.length > 0 && (
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)] mb-1.5">
            Open questions
          </div>
          <ul className="space-y-1 text-sm text-[var(--text-secondary)] list-disc list-inside">
            {session.open_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      {!session.summary && session.stories.length === 0 && (
        <div className="text-sm text-[var(--text-tertiary)] text-center py-8">
          Generate items from a transcript to see a summary here.
        </div>
      )}
    </div>
  )
}

function StoriesTab({ session, jiraConfigured }) {
  if (!session || session.stories.length === 0) {
    return (
      <div className="text-sm text-[var(--text-tertiary)] text-center py-8">
        No items yet — paste a transcript and click "Generate Items".
      </div>
    )
  }
  return (
    <div className="space-y-2">
      {session.stories.map((gs, i) => (
        <StoryCard
          key={gs.id || i}
          gs={gs}
          index={i}
          jiraResult={jiraResultFor(session, gs.id)}
          jiraConfigured={jiraConfigured}
        />
      ))}
    </div>
  )
}

function LogsTab({ session }) {
  const logs = session?.logs || []
  if (logs.length === 0) {
    return <div className="text-sm text-[var(--text-tertiary)] text-center py-8">No pipeline activity yet.</div>
  }
  return (
    <div className="space-y-1.5">
      {logs.map((l, i) => (
        <div key={i} className="text-xs text-[var(--text-secondary)] rounded-lg bg-[var(--bg-app)] px-3 py-2 flex gap-2">
          <span className="text-[var(--text-tertiary)] shrink-0">{new Date(l.ts).toLocaleTimeString()}</span>
          <span className="font-medium text-[var(--accent-strong)] shrink-0">[{l.stage}]</span>
          <span>{l.message}</span>
        </div>
      ))}
    </div>
  )
}

export default function RightPanel() {
  const { session, sending, config } = useSession()
  const [tab, setTab] = useState('Jira Items')
  const wasSending = useRef(false)

  useEffect(() => {
    if (sending && !wasSending.current) setTab('Workflow')
    wasSending.current = sending
  }, [sending])

  return (
    <div className="w-[420px] shrink-0 border-l border-[var(--border-subtle)] bg-[var(--bg-surface)] flex flex-col min-h-0">
      <div className="flex items-center justify-between px-3 pt-3">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                tab === t
                  ? 'bg-[var(--bg-hover)] text-[var(--text-primary)]'
                  : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        {session?.stories?.length > 0 && <ExportMenu />}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'Summary' && <SummaryTab session={session} />}
        {tab === 'Jira Items' && <StoriesTab session={session} jiraConfigured={config.jira_configured} />}
        {tab === 'Workflow' && <WorkflowTab />}
        {tab === 'Logs' && <LogsTab session={session} />}
      </div>
    </div>
  )
}
