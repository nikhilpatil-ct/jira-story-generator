import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'

const ConfirmContext = createContext(null)

export function ConfirmProvider({ children }) {
  const [dialog, setDialog] = useState(null)
  const resolver = useRef(null)

  const close = useCallback((result) => {
    if (resolver.current) {
      resolver.current(result)
      resolver.current = null
    }
    setDialog(null)
  }, [])

  const confirm = useCallback(
    (options = {}) =>
      new Promise((resolve) => {
        resolver.current = resolve
        setDialog({
          title: options.title ?? 'Are you sure?',
          message: options.message ?? '',
          confirmLabel: options.confirmLabel ?? 'Confirm',
          cancelLabel: options.cancelLabel ?? 'Cancel',
          danger: options.danger ?? false,
        })
      }),
    [],
  )

  useEffect(() => {
    if (!dialog) return
    const onKey = (e) => {
      if (e.key === 'Escape') close(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dialog, close])

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {createPortal(
        <AnimatePresence>
          {dialog && (
            <motion.div
              className="fixed inset-0 z-[110] flex items-center justify-center p-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="absolute inset-0 bg-black/50 backdrop-blur-[1px]" onClick={() => close(false)} />
              <motion.div
                role="dialog"
                aria-modal="true"
                initial={{ opacity: 0, scale: 0.95, y: 8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 8 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                className="relative w-full max-w-sm rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface-raised)] p-5 shadow-2xl shadow-black/40"
              >
                <div className="text-sm font-semibold text-[var(--text-primary)]">{dialog.title}</div>
                {dialog.message && <div className="mt-1.5 text-xs text-[var(--text-secondary)]">{dialog.message}</div>}
                <div className="mt-5 flex justify-end gap-2">
                  <button
                    onClick={() => close(false)}
                    className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)]"
                  >
                    {dialog.cancelLabel}
                  </button>
                  <button
                    autoFocus
                    onClick={() => close(true)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium text-white transition-colors ${
                      dialog.danger ? 'bg-[var(--danger)] hover:brightness-110' : 'bg-[var(--accent)] hover:bg-[var(--accent-strong)]'
                    }`}
                  >
                    {dialog.confirmLabel}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (!ctx) throw new Error('useConfirm must be used within a ConfirmProvider')
  return ctx
}
