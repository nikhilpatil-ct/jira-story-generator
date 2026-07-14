import { useSession } from '../state/SessionContext'

function AutoCreateToggle() {
  const { autoCreateJira, setAutoCreateJira, config } = useSession()

  return (
    <button
      onClick={() => setAutoCreateJira(!autoCreateJira)}
      disabled={!config.jira_configured}
      title={
        !config.jira_configured
          ? 'Configure JIRA to enable auto-create'
          : autoCreateJira
            ? 'New items are created in JIRA automatically'
            : 'New items wait for manual "Create" per item'
      }
      className="hidden md:flex items-center gap-2 text-xs rounded-full pl-3 pr-1 py-1 border border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
    >
      <span className="text-[var(--text-secondary)]">{autoCreateJira ? 'Auto-create in JIRA' : 'Manual JIRA create'}</span>
      <span
        className={`relative w-8 h-4.5 rounded-full transition-colors shrink-0 ${
          autoCreateJira ? 'bg-[var(--accent)]' : 'bg-[var(--border-strong)]'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full bg-white transition-transform ${
            autoCreateJira ? 'translate-x-3.5' : 'translate-x-0'
          }`}
        />
      </span>
    </button>
  )
}

export default function TopNavbar({ theme, onToggleTheme }) {
  const { session, config } = useSession()

  return (
    <header className="h-14 shrink-0 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] flex items-center justify-between px-4 gap-4">
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--accent-strong)] flex items-center justify-center text-white text-sm font-bold shrink-0">
          J
        </div>
        <span className="font-semibold text-sm shrink-0">JIRA Story Generator</span>
        {session && (
          <>
            <span className="text-[var(--text-tertiary)] shrink-0">/</span>
            <span className="text-sm text-[var(--text-secondary)] truncate">{session.title}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <AutoCreateToggle />

        <div
          title={config.jira_configured ? `JIRA project: ${config.jira_project_key}` : 'JIRA not configured'}
          className={`hidden sm:flex items-center gap-1.5 text-xs rounded-full px-3 py-1 border ${
            config.jira_configured
              ? 'border-[var(--success)]/40 text-[var(--success)]'
              : 'border-[var(--border-strong)] text-[var(--text-tertiary)]'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${config.jira_configured ? 'bg-[var(--success)]' : 'bg-[var(--text-tertiary)]'}`} />
          {config.jira_configured ? config.jira_project_key : 'JIRA not configured'}
        </div>

        <button
          onClick={onToggleTheme}
          title="Toggle theme"
          className="w-9 h-9 rounded-lg hover:bg-[var(--bg-hover)] flex items-center justify-center text-[var(--text-secondary)]"
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>

        <div className="w-8 h-8 rounded-full bg-[var(--bg-hover)] border border-[var(--border-subtle)] flex items-center justify-center text-xs font-medium text-[var(--text-secondary)]">
          U
        </div>
      </div>
    </header>
  )
}
