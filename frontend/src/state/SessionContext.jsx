import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../api'

const SessionCtx = createContext(null)

const STEP_LABELS = {
  idle: 'Idle',
  cleaning: 'Cleaning transcript',
  extracting: 'Extracting requirements',
  context: 'Loading app context',
  clarifying: 'Clarifying details',
  drafting: 'Drafting items',
  validating: 'Validating',
  done: 'Done',
}

export function SessionProvider({ children }) {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [session, setSession] = useState(null)
  const [config, setConfig] = useState({ jira_configured: false, jira_project_key: null, model: null })
  // The id of the session a generation run is currently in flight for (null when nothing is running).
  // Scoping this to a session — instead of a bare `sending` boolean — is what keeps a run from appearing
  // in a different session the user switches to while it's still going.
  const [runningSessionId, setRunningSessionId] = useState(null)
  const [stopping, setStopping] = useState(false)
  const [currentStep, setCurrentStep] = useState('idle')
  const [error, setError] = useState(null)
  const [autoCreateJira, setAutoCreateJiraState] = useState(
    () => localStorage.getItem('auto_create_jira') === 'true'
  )
  const pollRef = useRef(null)
  // Latest active session id, readable synchronously from the polling/async callbacks (which would
  // otherwise close over a stale `activeSessionId`).
  const activeSessionIdRef = useRef(null)

  // The run is only "sending" from the perspective of the session it actually belongs to; any other
  // session the user is viewing sees a normal, idle UI.
  const sending = runningSessionId !== null && runningSessionId === activeSessionId

  const setAutoCreateJira = useCallback((value) => {
    setAutoCreateJiraState(value)
    localStorage.setItem('auto_create_jira', String(value))
  }, [])

  const refreshSessions = useCallback(async () => {
    const list = await api.listSessions()
    setSessions(list)
    return list
  }, [])

  const loadSession = useCallback(async (id) => {
    const full = await api.getSession(id)
    setSession(full)
    setCurrentStep(full.current_step || 'idle')
    return full
  }, [])

  const selectSession = useCallback(
    async (id) => {
      // Update the ref synchronously so the running session's poller stops driving the on-screen
      // session the moment we switch away, even before React commits the state change below.
      activeSessionIdRef.current = id
      setActiveSessionId(id)
      localStorage.setItem('active_session_id', id)
      await loadSession(id)
    },
    [loadSession]
  )

  const newSession = useCallback(async () => {
    const created = await api.createSession()
    await refreshSessions()
    await selectSession(created.id)
    return created
  }, [refreshSessions, selectSession])

  useEffect(() => {
    async function init() {
      const [list] = await Promise.all([
        refreshSessions(),
        api.getConfig().then(setConfig).catch(() => {}),
      ])
      const stored = localStorage.getItem('active_session_id')
      const target = list.find((s) => s.id === stored) ? stored : list[0]?.id
      if (target) {
        await selectSession(target)
      } else {
        await newSession()
      }
    }
    init().catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (id) => {
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const full = await api.getSession(id)
          // Only drive the displayed session/step when the run's session is the one on screen — otherwise
          // a background run would clobber whatever session the user has since switched to.
          if (activeSessionIdRef.current === id) {
            setCurrentStep(full.current_step || 'idle')
            setSession(full)
          }
          // Reflect a mid-run auto-rename (and freshness) in the sidebar list regardless of what's on
          // screen, without a full refetch.
          setSessions((prev) =>
            prev.map((s) => (s.id === id ? { ...s, title: full.title, updated_at: full.updated_at } : s))
          )
        } catch {
          // ignore transient poll errors
        }
      }, 600)
    },
    [stopPolling]
  )

  useEffect(() => stopPolling, [stopPolling])

  const sendMessage = useCallback(
    async (text, sourceType = null) => {
      if (!activeSessionId || !text.trim()) return null
      // One run at a time: the single poller can only track one in-flight run. If another is going
      // (even in a different session), ask the user to wait rather than corrupting it.
      if (runningSessionId) {
        if (runningSessionId !== activeSessionId) {
          setError('A generation is still running in another session — wait for it to finish or stop it first.')
        }
        return null
      }
      const runId = activeSessionId
      setRunningSessionId(runId)
      setError(null)
      startPolling(runId)
      try {
        const result = await api.chat(runId, text, autoCreateJira, sourceType)
        const full = await api.getSession(runId)
        // Only push the finished run's result onto the screen if the user is still viewing that session.
        if (activeSessionIdRef.current === runId) {
          setSession(full)
        }
        await refreshSessions()
        return { result, full }
      } catch (err) {
        setError(err.message)
        throw err
      } finally {
        stopPolling()
        setRunningSessionId(null)
        setStopping(false)
        if (activeSessionIdRef.current === runId) setCurrentStep('idle')
      }
    },
    [activeSessionId, runningSessionId, autoCreateJira, startPolling, stopPolling, refreshSessions]
  )

  // Ask the server to cancel the in-flight generation run. The still-open /api/chat request then
  // returns its "stopped" reply on its own, which flips `sending` back off via sendMessage's finally.
  const stopGeneration = useCallback(async () => {
    // Only stoppable from the session the run actually belongs to (which is the only place the Stop
    // button is shown anyway).
    if (!activeSessionId || runningSessionId !== activeSessionId) return
    setStopping(true)
    try {
      await api.stopGeneration(activeSessionId)
    } catch {
      // The run may have finished between render and click — nothing to stop, ignore.
    }
  }, [activeSessionId, runningSessionId])

  const submitClarification = useCallback(
    async (groupId, answers, skip = false) => {
      if (!activeSessionId) return null
      const result = await api.submitClarification(activeSessionId, groupId, answers, skip)
      // Refresh immediately so the answered item drops out of the form without waiting for the next poll
      // tick; the drafting run (still in the open /api/chat request) resumes server-side on its own.
      await loadSession(activeSessionId).catch(() => {})
      return result
    },
    [activeSessionId, loadSession]
  )

  const renameSession = useCallback(
    async (id, title) => {
      await api.patchSession(id, { title })
      await refreshSessions()
      if (id === activeSessionId) setSession((s) => (s ? { ...s, title } : s))
    },
    [activeSessionId, refreshSessions]
  )

  const toggleFavorite = useCallback(
    async (id, favorite) => {
      await api.patchSession(id, { favorite })
      await refreshSessions()
      if (id === activeSessionId) setSession((s) => (s ? { ...s, favorite } : s))
    },
    [activeSessionId, refreshSessions]
  )

  const deleteSessionById = useCallback(
    async (id) => {
      await api.deleteSession(id)
      const list = await refreshSessions()
      if (id === activeSessionId) {
        const next = list[0]?.id
        if (next) await selectSession(next)
        else await newSession()
      }
    },
    [activeSessionId, refreshSessions, selectSession, newSession]
  )

  const runStoryAction = useCallback(
    async (index, action, instructions) => {
      if (!activeSessionId) return null
      const updated = await api.storyAction(activeSessionId, index, action, instructions)
      setSession((s) => {
        if (!s) return s
        const stories = [...s.stories]
        stories[index] = updated
        return { ...s, stories }
      })
      return updated
    },
    [activeSessionId]
  )

  const value = {
    sessions,
    activeSessionId,
    session,
    config,
    sending,
    stopping,
    stopGeneration,
    currentStep,
    currentStepLabel: STEP_LABELS[currentStep] || currentStep,
    autoCreateJira,
    setAutoCreateJira,
    error,
    setError,
    selectSession,
    newSession,
    sendMessage,
    renameSession,
    toggleFavorite,
    deleteSession: deleteSessionById,
    runStoryAction,
    submitClarification,
    refreshSessions,
    refreshActiveSession: () => (activeSessionId ? loadSession(activeSessionId) : Promise.resolve(null)),
  }

  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>
}

export function useSession() {
  const ctx = useContext(SessionCtx)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
