import { useEffect, useRef, useState } from 'react'
import './App.css'

const SESSION_KEY = 'jira_story_generator_session_id'

const WELCOME_MESSAGE = {
  role: 'assistant',
  text:
    "Hi! Paste your meeting notes, requirements doc, or feature idea below and I'll turn it into " +
    'structured, validated JIRA stories. I may ask a clarifying question first if something important ' +
    'is missing.',
}

function ChatMessage({ role, text }) {
  return <div className={`message ${role}`}>{text}</div>
}

function App() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const logRef = useRef(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [messages, sending])

  function getSessionId() {
    return localStorage.getItem(SESSION_KEY)
  }

  function setSessionId(id) {
    localStorage.setItem(SESSION_KEY, id)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || sending) return

    setMessages((prev) => [...prev, { role: 'user', text: trimmed }])
    setInput('')
    setSending(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: getSessionId(), message: trimmed }),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        setMessages((prev) => [
          ...prev,
          { role: 'error', text: body.detail || `Request failed (${response.status})` },
        ])
        return
      }

      const data = await response.json()
      setSessionId(data.session_id)
      setMessages((prev) => [...prev, { role: 'assistant', text: data.reply }])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'error', text: `Network error: ${err.message}` }])
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit(event)
    }
  }

  async function handleNewConversation() {
    const sessionId = getSessionId()
    if (sessionId) {
      try {
        await fetch(`/api/reset?session_id=${encodeURIComponent(sessionId)}`, { method: 'POST' })
      } catch {
        // ignore - resetting locally is enough even if the backend call fails
      }
    }
    localStorage.removeItem(SESSION_KEY)
    setMessages([
      { role: 'assistant', text: 'Started a new conversation. Paste your meeting notes or feature idea below.' },
    ])
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI JIRA Story Generator</h1>
        <p>Paste meeting notes or a feature description. I'll turn them into validated JIRA stories.</p>
        <button className="new-chat-btn" onClick={handleNewConversation} title="Start a new conversation">
          New conversation
        </button>
      </header>

      <main className="chat-log" ref={logRef}>
        {messages.map((m, i) => (
          <ChatMessage key={i} role={m.role} text={m.text} />
        ))}
        {sending && <div className="message pending">Thinking...</div>}
      </main>

      <form className="chat-form" onSubmit={handleSubmit}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Paste meeting notes, describe a feature, or reply to my question..."
          rows={3}
          required
        />
        <button type="submit" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}

export default App
