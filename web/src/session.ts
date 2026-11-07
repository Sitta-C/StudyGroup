// Only the opaque credential and its expiry persist; never passwords or chat data.
export const SESSION_STORAGE_KEY = 'studygroup.session.v1'
export type StoredSession = { resume_token: string; expires_at: number }

export function readSession(): StoredSession | null {
  try {
    const value = localStorage.getItem(SESSION_STORAGE_KEY)
    if (value === null) return null
    const session = JSON.parse(value) as StoredSession | null
    if (session && typeof session.resume_token === 'string' && /^[A-Za-z0-9_-]{43}$/.test(session.resume_token)
        && Number.isSafeInteger(session.expires_at) && session.expires_at > Date.now() / 1000) return session
    localStorage.removeItem(SESSION_STORAGE_KEY)
  } catch {
    // Storage may be blocked, full, or contain malformed data. Login still works.
    try { localStorage.removeItem(SESSION_STORAGE_KEY) } catch { /* Storage is unavailable. */ }
  }
  return null
}

export function saveSession(session: StoredSession): boolean {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ resume_token: session.resume_token, expires_at: session.expires_at }))
    return true
  } catch { return false }
}

export function clearSession(token?: string) {
  try {
    // A delayed failure must not delete a newer login saved by another tab.
    if (token !== undefined && readSession()?.resume_token !== token) return
    localStorage.removeItem(SESSION_STORAGE_KEY)
  } catch { /* Storage is unavailable. */ }
}
