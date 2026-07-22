import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'

const ToastContext = createContext(null)

const VARIANT_STYLES = {
  error: { border: 'border-[var(--danger)]/40', icon: '⚠', iconColor: 'text-[var(--danger)]' },
  success: { border: 'border-[var(--success)]/40', icon: '✓', iconColor: 'text-[var(--success)]' },
  info: { border: 'border-[var(--border-strong)]', icon: 'ℹ', iconColor: 'text-[var(--accent-strong)]' },
}

let idCounter = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const show = useCallback(
    (message, options = {}) => {
      const { variant = 'error', duration = 5000, title } = options
      const id = ++idCounter
      setToasts((list) => [...list, { id, message, variant, title }])
      if (duration > 0) {
        timers.current.set(id, setTimeout(() => dismiss(id), duration))
      }
      return id
    },
    [dismiss],
  )

  const api = useMemo(
    () => ({
      show,
      dismiss,
      error: (message, options) => show(message, { ...options, variant: 'error' }),
      success: (message, options) => show(message, { ...options, variant: 'success' }),
      info: (message, options) => show(message, { ...options, variant: 'info' }),
    }),
    [show, dismiss],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div className="fixed bottom-4 right-4 z-[100] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2 pointer-events-none">
          <AnimatePresence initial={false}>
            {toasts.map((t) => {
              const style = VARIANT_STYLES[t.variant] ?? VARIANT_STYLES.info
              return (
                <motion.div
                  key={t.id}
                  layout
                  initial={{ opacity: 0, x: 24, scale: 0.96 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  exit={{ opacity: 0, x: 24, scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  role="alert"
                  className={`pointer-events-auto flex items-start gap-2.5 rounded-xl border ${style.border} bg-[var(--bg-surface-raised)] px-3.5 py-3 shadow-lg shadow-black/25`}
                >
                  <span className={`text-sm leading-5 shrink-0 ${style.iconColor}`}>{style.icon}</span>
                  <div className="min-w-0 flex-1">
                    {t.title && <div className="mb-0.5 text-xs font-semibold text-[var(--text-primary)]">{t.title}</div>}
                    <div className="text-xs text-[var(--text-secondary)] break-words">{t.message}</div>
                  </div>
                  <button
                    onClick={() => dismiss(t.id)}
                    aria-label="Dismiss notification"
                    className="shrink-0 text-sm leading-none text-[var(--text-tertiary)] transition-colors hover:text-[var(--text-primary)]"
                  >
                    ✕
                  </button>
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}
