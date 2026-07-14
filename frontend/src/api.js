const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function handle(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const error = new Error(body.detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return response.json()
  return response.text()
}

export const api = {
  getConfig: () => fetch('/api/config').then(handle),

  listSessions: () => fetch('/api/sessions').then(handle),

  createSession: () => fetch('/api/sessions', { method: 'POST' }).then(handle),

  getSession: (id) => fetch(`/api/sessions/${id}`).then(handle),

  patchSession: (id, patch) =>
    fetch(`/api/sessions/${id}`, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(patch) }).then(
      handle
    ),

  deleteSession: (id) => fetch(`/api/sessions/${id}`, { method: 'DELETE' }).then(handle),

  uploadFile: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch('/api/upload', { method: 'POST', body: form }).then(handle)
  },

  chat: (sessionId, message, autoCreateJira = false) =>
    fetch('/api/chat', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ session_id: sessionId, message, auto_create_jira: autoCreateJira }),
    }).then(handle),

  storyAction: (sessionId, index, action, instructions) =>
    fetch(`/api/stories/${sessionId}/${index}/action`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ action, instructions }),
    }).then(handle),

  jiraPreview: (sessionId, index) => fetch(`/api/sessions/${sessionId}/jira-preview/${index}`).then(handle),

  jiraRetry: (sessionId, index) =>
    fetch('/api/jira/retry', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ session_id: sessionId, index }),
    }).then(handle),

  exportUrl: (sessionId, format) => `/api/export/${sessionId}?format=${format}`,
}
