import { useEffect, useRef, useState } from 'react'
import { useSession } from '../state/SessionContext'
import ClarifyingQuestions from './ClarifyingQuestions'

const QUICK_COMMANDS = [
  'Generate bugs only',
  'Generate the epic',
  'Regenerate',
  'Create these in JIRA',
]

const TRANSCRIPT_DISPLAY_THRESHOLD = 240

// While the pipeline is on one of these steps, the Workflow panel already shows live progress, so the chat
// area stays quiet. The chat loader only appears once the workflow is done (or for a plain chat with no
// workflow at all), covering the gap between "workflow done" and the reply actually landing in the chat.
const WORKFLOW_STEPS = ['cleaning', 'extracting', 'context', 'clarifying', 'drafting', 'validating']

function displayFor(message) {
  if (message.role === 'user' && message.content.length > TRANSCRIPT_DISPLAY_THRESHOLD) {
    return '📄 Transcript uploaded by user'
  }
  return message.content
}

function ChatLoader() {
  return (
    <div className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
      <span className="w-3.5 h-3.5 rounded-full border-2 border-[var(--accent)] border-t-transparent animate-spin shrink-0" />
      Loading chat…
    </div>
  )
}

export default function PromptBox() {
  const { session, sendMessage, sending, stopping, stopGeneration, error, currentStep } = useSession()
  const [input, setInput] = useState('')
  const logRef = useRef(null)

  const history = session?.history || []
  const hasPendingQuestions = (session?.pending_questions?.length ?? 0) > 0
  const workflowRunning = sending && WORKFLOW_STEPS.includes(currentStep)
  // Waiting on the reply, but not mid-workflow (that shows in the Workflow panel) and not blocked on questions.
  const chatLoading = sending && !workflowRunning && !hasPendingQuestions

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [history.length, sending, currentStep])

  async function submit(text) {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    setInput('')
    try {
      await sendMessage(trimmed)
    } catch {
      // error surfaced via context
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(input)
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 gap-2">
      {history.length > 0 && (
        <div
          ref={logRef}
          className="flex-1 min-h-0 overflow-y-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3 space-y-2"
        >
          {history.map((m, i) => (
            <div
              key={i}
              className={`text-xs leading-relaxed whitespace-pre-wrap ${
                m.role === 'user' ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'
              }`}
            >
              <span className="font-medium mr-1.5">{m.role === 'user' ? 'You:' : 'AI:'}</span>
              {displayFor(m)}
            </div>
          ))}
          {chatLoading && <ChatLoader />}
        </div>
      )}

      {hasPendingQuestions && <ClarifyingQuestions />}

      {history.length === 0 && (
        <div className="flex-1 min-h-0 flex items-center justify-center rounded-xl border border-dashed border-[var(--border-subtle)] text-sm text-[var(--text-tertiary)] text-center px-8">
          {chatLoading ? (
            <ChatLoader />
          ) : (
            'Upload a transcript and click "Generate Items", or type a message below to get started.'
          )}
        </div>
      )}

      {error && (
        <div className="text-xs text-[var(--danger)] rounded-lg border border-[var(--danger)]/40 px-3 py-1.5">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {QUICK_COMMANDS.map((cmd) => (
          <button
            key={cmd}
            onClick={() => submit(cmd)}
            disabled={sending}
            className="text-xs px-2.5 py-1 rounded-full border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] transition-colors disabled:opacity-50"
          >
            {cmd}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(input)
        }}
        className="flex items-end gap-2 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder='Ask a question, request a revision ("make item 2 high priority"), or type a command…'
          className="flex-1 resize-none bg-transparent outline-none text-sm px-2 py-1.5 max-h-28"
        />
        {sending ? (
          <button
            type="button"
            onClick={stopGeneration}
            disabled={stopping}
            title="Stop the current run"
            className="px-4 py-1.5 rounded-lg bg-[var(--danger)] hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            {stopping ? 'Stopping…' : 'Stop'}
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-1.5 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-strong)] disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
          >
            Send
          </button>
        )}
      </form>
    </div>
  )
}
