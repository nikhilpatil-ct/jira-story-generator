import { useState } from 'react'
import { SessionProvider } from './state/SessionContext'
import { ToastProvider } from './state/ToastContext'
import { ConfirmProvider } from './state/ConfirmContext'
import { useTheme } from './state/useTheme'
import Sidebar from './components/Sidebar'
import TopNavbar from './components/TopNavbar'
import TranscriptEditor from './components/TranscriptEditor'
import PromptBox from './components/PromptBox'
import RightPanel from './components/RightPanel'

function Shell() {
  const [collapsed, setCollapsed] = useState(false)
  const [theme, toggleTheme] = useTheme()

  return (
    <div className="h-full flex flex-col">
      <TopNavbar theme={theme} onToggleTheme={toggleTheme} />
      <div className="flex-1 flex min-h-0">
        <Sidebar collapsed={collapsed} onToggleCollapsed={() => setCollapsed((c) => !c)} />
        <main className="flex-1 flex flex-col min-w-0 p-4 gap-3">
          <TranscriptEditor />
          <PromptBox />
        </main>
        <RightPanel />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <SessionProvider>
          <Shell />
        </SessionProvider>
      </ConfirmProvider>
    </ToastProvider>
  )
}
