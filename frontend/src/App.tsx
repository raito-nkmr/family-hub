import { useCallback, useEffect, useState } from 'react'
import { Route, Routes, useLocation, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import './styles.css'
import { AuthenticatedApp } from './app/AuthenticatedApp'
import { getCurrentSession, login, type AuthUser } from './features/auth/api'
import { LoginScreen } from './features/auth/components/LoginScreen'
import { InvitationAcceptanceScreen } from './features/invitations/InvitationAcceptanceScreen'
import { PrivacyPage } from './features/privacy/PrivacyPage'
import { isAbortError, isUnauthorizedError } from './shared/api/errors'
import type { Theme } from './shared/types/theme'
import { AppFooter } from './shared/ui/AppFooter'

const THEME_STORAGE_KEY = 'family-hub-theme'

function readInvitationToken(hash: string): string | null {
  const token = new URLSearchParams(hash.slice(1)).get('invite')
  return token?.trim() || null
}

function App() {
  const { t, i18n } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null)
  const [sessionCheckCompleted, setSessionCheckCompleted] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light',
  )
  const invitationToken = readInvitationToken(location.hash)
  const isPrivacyPath = location.pathname === '/privacy'
  const shouldRestoreSession =
    invitationToken === null && !isPrivacyPath && currentUser === null && !sessionCheckCompleted

  useEffect(() => {
    if (!shouldRestoreSession) return
    const controller = new AbortController()
    const checkSession = async () => {
      try {
        setCurrentUser(await getCurrentSession(controller.signal))
      } catch (error) {
        if (isAbortError(error)) return
        if (!isUnauthorizedError(error)) setAuthError(i18n.t('auth.checkFailed'))
      } finally {
        if (!controller.signal.aborted) setSessionCheckCompleted(true)
      }
    }
    void checkSession()
    return () => controller.abort()
  }, [i18n, shouldRestoreSession])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // The selected theme still applies when browser storage is unavailable.
    }
    document
      .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
      ?.setAttribute('content', theme === 'dark' ? '#0b1726' : '#d8e2ed')
  }, [theme])

  const handleLogin = async (username: string, password: string) => {
    setCurrentUser(await login(username, password))
    setAuthError(null)
  }

  const toggleTheme = () => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  const handleSessionEnded = useCallback(() => setCurrentUser(null), [])

  const continueToLogin = () => {
    navigate(`${location.pathname}${location.search}`, { replace: true })
  }

  if (invitationToken) {
    return (
      <InvitationAcceptanceScreen
        token={invitationToken}
        theme={theme}
        onContinueToLogin={continueToLogin}
        onToggleTheme={toggleTheme}
      />
    )
  }

  if (isPrivacyPath) {
    return (
      <div className="public-shell">
        <PrivacyPage theme={theme} onToggleTheme={toggleTheme} />
        <AppFooter privacyCurrent />
      </div>
    )
  }

  if (shouldRestoreSession) {
    return (
      <main className="session-loading" aria-label={t('auth.checking')}>
        <span className="spinner" />
      </main>
    )
  }

  if (currentUser) {
    return (
      <AuthenticatedApp
        currentUser={currentUser}
        theme={theme}
        onSessionEnded={handleSessionEnded}
        onCurrentUserChanged={setCurrentUser}
        onToggleTheme={toggleTheme}
      />
    )
  }

  return (
    <Routes>
      <Route
        path="*"
        element={
          <div className="public-shell">
            <LoginScreen initialError={authError} theme={theme} onLogin={handleLogin} onToggleTheme={toggleTheme} />
            <AppFooter />
          </div>
        }
      />
    </Routes>
  )
}

export default App
