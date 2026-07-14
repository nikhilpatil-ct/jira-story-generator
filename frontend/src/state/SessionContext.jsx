import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../api'

const SessionCtx = createContext(null)

const STEP_LABELS = {
  idle: 'Idle',
  cleaning: 'Cleaning transcript',
  extracting: 'Extracting requirements',
  drafting: 'Drafting items',
  validating: 'Validating',
  done: 'Done',
}

export function SessionProvider({ children }) {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [session, setSession] = useState(null)
  const [config, setConfig] = useState({ jira_configured: false, jira_project_key: null, model: null })
  const [sending, setSending] = useState(false)
  const [currentStep, setCurrentStep] = useState('idle')
  const [error, setError] = useState(null)
  const [autoCreateJira, setAutoCreateJiraState] = useState(
    () => localStorage.getItem('auto_create_jira') === 'true'
  )
  const pollRef = useRef(null)

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
          setCurrentStep(full.current_step || 'idle')
          setSession(full)
        } catch {
          // ignore transient poll errors
        }
      }, 600)
    },
    [stopPolling]
  )

  useEffect(() => stopPolling, [stopPolling])

  const sendMessage = useCallback(
    async (text) => {
      if (!activeSessionId || !text.trim() || sending) return null
      setSending(true)
      setError(null)
      startPolling(activeSessionId)
      try {
        const result = await api.chat(activeSessionId, text, autoCreateJira)
        const full = await loadSession(activeSessionId)
        await refreshSessions()
        return { result, full }
      } catch (err) {
        setError(err.message)
        throw err
      } finally {
        stopPolling()
        setCurrentStep('idle')
        setSending(false)
      }
    },
    [activeSessionId, sending, autoCreateJira, startPolling, stopPolling, loadSession, refreshSessions]
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
