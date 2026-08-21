import { Suspense, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { logout, type AuthUser } from '../features/auth/api'
import { RequiredPasswordChangeScreen } from '../features/auth/RequiredPasswordChangeScreen'
import { PhotoMediaCacheProvider } from '../features/photos/components/PhotoMediaCacheProvider'
import { StorageStatusPill } from '../features/photos/components/StorageStatusPill'
import { isUnauthorizedError } from '../shared/api/errors'
import { queryClient } from '../shared/api/queryClient'
import type { Theme } from '../shared/types/theme'
import { AppFooter } from '../shared/ui/AppFooter'
import { AppHeader } from '../shared/ui/AppHeader'
import { AppNavigation, SectionNavigation } from '../shared/ui/AppNavigation'
import { PullToRefreshIndicator } from '../shared/ui/PullToRefreshIndicator'
import { AuthenticatedAppOverlays } from './AuthenticatedAppOverlays'
import { AuthenticatedAppRoutes } from './AuthenticatedAppRoutes'
import { useAuthenticatedAppState } from './useAuthenticatedAppState'
import { appPaths, getAppView, photoViews } from './routes'

interface AuthenticatedAppProps {
  currentUser: AuthUser
  theme: Theme
  onSessionEnded: () => void
  onCurrentUserChanged: (user: AuthUser) => void
  onToggleTheme: () => void
}

export function AuthenticatedApp({
  currentUser,
  theme,
  onSessionEnded,
  onCurrentUserChanged,
  onToggleTheme,
}: AuthenticatedAppProps) {
  if (currentUser.must_change_password) {
    return (
      <RequiredPasswordChangeScreen
        username={currentUser.username}
        theme={theme}
        onSessionEnded={onSessionEnded}
        onToggleTheme={onToggleTheme}
      />
    )
  }

  return (
    <PhotoMediaCacheProvider>
      <AuthenticatedAppShell
        currentUser={currentUser}
        theme={theme}
        onSessionEnded={onSessionEnded}
        onCurrentUserChanged={onCurrentUserChanged}
        onToggleTheme={onToggleTheme}
      />
    </PhotoMediaCacheProvider>
  )
}

function AuthenticatedAppShell({
  currentUser,
  theme,
  onSessionEnded,
  onCurrentUserChanged,
  onToggleTheme,
}: AuthenticatedAppProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const activeView = getAppView(location.pathname)
  const resetPhotoDashboardRef = useRef<() => void>(() => undefined)
  const closePhotoRef = useRef<() => void>(() => undefined)
  const previousPathRef = useRef(location.pathname)

  const handleUnauthorized = useCallback(() => {
    resetPhotoDashboardRef.current()
    queryClient.clear()
    onSessionEnded()
    navigate(appPaths.home, { replace: true })
  }, [navigate, onSessionEnded])
  const { photoDashboard, photoActivity, pwaInstall, pullToRefresh } = useAuthenticatedAppState({
    currentUserId: currentUser.id,
    activeView,
    onUnauthorized: handleUnauthorized,
  })

  useEffect(() => {
    resetPhotoDashboardRef.current = photoDashboard.reset
    closePhotoRef.current = photoDashboard.closePhoto
  }, [photoDashboard.reset, photoDashboard.closePhoto])

  useEffect(() => {
    if (previousPathRef.current === location.pathname) return
    previousPathRef.current = location.pathname
    closePhotoRef.current()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [location.pathname])

  const handleLogout = async () => {
    try {
      await logout()
      photoDashboard.reset()
      queryClient.clear()
      onSessionEnded()
      navigate(appPaths.home, { replace: true })
    } catch (error) {
      if (isUnauthorizedError(error)) {
        handleUnauthorized()
        return
      }
      photoDashboard.reportError(t('auth.logoutFailed'))
    }
  }

  const privateShell = (
    <div className="app-shell">
      <PullToRefreshIndicator {...pullToRefresh} />
      <AppHeader
        username={currentUser.username}
        theme={theme}
        status={
          activeView && ['home', ...photoViews].includes(activeView) ? (
            <StorageStatusPill storage={photoDashboard.storage} />
          ) : undefined
        }
        onLogout={() => void handleLogout()}
        onToggleTheme={onToggleTheme}
      />

      <div className="app-workspace">
        <AppNavigation
          showInvitations={currentUser.system_role === 'admin'}
          photoUnseenCount={photoActivity.unseenCount}
        />
        <div className="app-content">
          <SectionNavigation
            showInvitations={currentUser.system_role === 'admin'}
            photoUnseenCount={photoActivity.unseenCount}
          />
          <AuthenticatedAppRoutes
            currentUser={currentUser}
            activeView={activeView}
            onUnauthorized={handleUnauthorized}
            onCurrentUserChanged={onCurrentUserChanged}
            photoActivity={photoActivity}
            photoDashboard={photoDashboard}
            pwaInstall={pwaInstall}
          />
          <AppFooter privacyReturnTo={`${location.pathname}${location.search}`} />
        </div>
      </div>

      <AuthenticatedAppOverlays
        currentUserId={currentUser.id}
        photoDashboard={photoDashboard}
        pwaInstall={pwaInstall}
      />
    </div>
  )

  return (
    <Suspense
      fallback={
        <main className="session-loading" aria-label={t('common.loading')}>
          <span className="spinner" />
        </main>
      }
    >
      {privateShell}
    </Suspense>
  )
}
