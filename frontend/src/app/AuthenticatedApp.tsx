import { lazy, Suspense, useCallback, useEffect, useRef } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { logout, type AuthUser } from '../features/auth/api'
import { RequiredPasswordChangeScreen } from '../features/auth/RequiredPasswordChangeScreen'
import { PhotoModal } from '../features/photos/components/PhotoModal'
import { StorageStatusPill } from '../features/photos/components/StorageStatusPill'
import { usePhotoActivity } from '../features/photos/usePhotoActivity'
import { usePhotoDashboard } from '../features/photos/usePhotoDashboard'
import { PrivacyPage } from '../features/privacy/PrivacyPage'
import { PwaInstallGuide } from '../features/pwa/PwaInstallGuide'
import { usePwaInstallGuide } from '../features/pwa/usePwaInstallGuide'
import { isUnauthorizedError } from '../shared/api/errors'
import { queryClient } from '../shared/api/queryClient'
import type { Theme } from '../shared/types/theme'
import { AppFooter } from '../shared/ui/AppFooter'
import { AppHeader } from '../shared/ui/AppHeader'
import { AppNavigation, SectionNavigation } from '../shared/ui/AppNavigation'
import { appPaths, getAppView, photoViews } from './routes'
import { RequireAdmin } from './routeGuards'

const AccountPage = lazy(() =>
  import('../features/auth/AccountPage').then((module) => ({ default: module.AccountPage })),
)
const AlbumPage = lazy(() => import('../features/albums/AlbumPage').then((module) => ({ default: module.AlbumPage })))
const CleaningPage = lazy(() =>
  import('../features/cleaning/CleaningPage').then((module) => ({ default: module.CleaningPage })),
)
const GroupPage = lazy(() => import('../features/groups/GroupPage').then((module) => ({ default: module.GroupPage })))
const HomeRoute = lazy(() => import('../features/home/HomeRoute').then((module) => ({ default: module.HomeRoute })))
const InvitationAdminPage = lazy(() =>
  import('../features/invitations/InvitationAdminPage').then((module) => ({ default: module.InvitationAdminPage })),
)
const PhotoActivityRoute = lazy(() =>
  import('../features/photos/PhotoRoutes').then((module) => ({ default: module.PhotoActivityRoute })),
)
const PhotoRoute = lazy(() =>
  import('../features/photos/PhotoRoutes').then((module) => ({ default: module.PhotoRoute })),
)
const PhotoTrashPage = lazy(() =>
  import('../features/photos/PhotoTrashPage').then((module) => ({ default: module.PhotoTrashPage })),
)
const ShoppingPage = lazy(() =>
  import('../features/shopping/ShoppingPage').then((module) => ({ default: module.ShoppingPage })),
)
const SystemStatusPage = lazy(() =>
  import('../features/maintenance/SystemStatusPage').then((module) => ({ default: module.SystemStatusPage })),
)

interface AuthenticatedAppProps {
  currentUser: AuthUser
  theme: Theme
  onSessionEnded: () => void
  onToggleTheme: () => void
}

export function AuthenticatedApp({ currentUser, theme, onSessionEnded, onToggleTheme }: AuthenticatedAppProps) {
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
    <AuthenticatedAppShell
      currentUser={currentUser}
      theme={theme}
      onSessionEnded={onSessionEnded}
      onToggleTheme={onToggleTheme}
    />
  )
}

function AuthenticatedAppShell({ currentUser, theme, onSessionEnded, onToggleTheme }: AuthenticatedAppProps) {
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

  const photoDashboard = usePhotoDashboard({
    enabled: true,
    libraryEnabled: activeView === 'photos',
    storageEnabled: activeView !== null && ['home', ...photoViews].includes(activeView),
    onUnauthorized: handleUnauthorized,
  })
  const photoActivity = usePhotoActivity({
    enabled: true,
    userId: currentUser.id,
    active: activeView === 'photo-activity',
    onUnauthorized: handleUnauthorized,
  })
  const pwaInstall = usePwaInstallGuide()

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
          <Routes>
            <Route
              path={appPaths.home}
              element={
                <HomeRoute
                  userId={currentUser.id}
                  active={activeView === 'home'}
                  onUnauthorized={handleUnauthorized}
                  photoActivity={photoActivity}
                  photoDashboard={photoDashboard}
                  pwaInstall={pwaInstall}
                />
              }
            />
            <Route
              path={appPaths['photo-activity']}
              element={<PhotoActivityRoute activity={photoActivity} onSelectPhoto={photoDashboard.selectPhoto} />}
            />
            <Route
              path={appPaths.photos}
              element={<PhotoRoute currentUserId={currentUser.id} dashboard={photoDashboard} />}
            />
            <Route
              path={appPaths.albums}
              element={<AlbumPage onUnauthorized={handleUnauthorized} onSelectPhoto={photoDashboard.selectPhoto} />}
            />
            <Route
              path={appPaths['photo-trash']}
              element={
                <PhotoTrashPage
                  onUnauthorized={handleUnauthorized}
                  onLibraryChanged={() => void photoDashboard.refresh()}
                />
              }
            />
            <Route path={appPaths.cleaning} element={<CleaningPage onUnauthorized={handleUnauthorized} />} />
            <Route path={appPaths.shopping} element={<ShoppingPage onUnauthorized={handleUnauthorized} />} />
            <Route
              path={appPaths.groups}
              element={<GroupPage currentUserId={currentUser.id} onUnauthorized={handleUnauthorized} />}
            />
            <Route
              path={appPaths.account}
              element={
                <AccountPage
                  username={currentUser.username}
                  onSessionEnded={handleUnauthorized}
                  showPwaInstallGuideEntry={pwaInstall.installGuideAvailable}
                  onShowPwaInstallGuide={pwaInstall.openGuide}
                />
              }
            />
            <Route
              path={appPaths.invitations}
              element={
                <RequireAdmin role={currentUser.system_role}>
                  <InvitationAdminPage onUnauthorized={handleUnauthorized} />
                </RequireAdmin>
              }
            />
            <Route
              path={appPaths.system}
              element={
                <RequireAdmin role={currentUser.system_role}>
                  <SystemStatusPage onUnauthorized={handleUnauthorized} />
                </RequireAdmin>
              }
            />
            <Route path="*" element={<Navigate to={appPaths.home} replace />} />
          </Routes>
          <AppFooter privacyReturnTo={location.pathname} />
        </div>
      </div>

      {photoDashboard.selectedPhoto && (
        <PhotoModal
          photo={photoDashboard.selectedPhoto}
          photoDetailLoading={photoDashboard.photoDetailLoading}
          photoDetailError={photoDashboard.photoDetailError}
          currentUserId={currentUser.id}
          updatingMetadata={photoDashboard.updatingMetadata}
          error={photoDashboard.metadataError}
          groups={photoDashboard.groups}
          onClose={photoDashboard.closePhoto}
          onSharingChange={(groupIds) => void photoDashboard.changeSharing(groupIds)}
          onToggleFavorite={() => void photoDashboard.toggleFavorite()}
          onMemoSave={(memo) => void photoDashboard.savePhotoMetadata({ memo })}
          onCaptureDateSave={(capturedAt) =>
            void photoDashboard.savePhotoMetadata({ captured_at_override: capturedAt })
          }
          onTrash={() => void photoDashboard.moveSelectedPhotoToTrash()}
          onRetryPhotoDetail={() => void photoDashboard.retryPhotoDetail()}
          onModerateGroupShare={(groupId, password) => void photoDashboard.moderateGroupShare(groupId, password)}
          onPreviousPhoto={
            photoDashboard.previousPhoto
              ? () => void photoDashboard.selectPhoto(photoDashboard.previousPhoto!)
              : undefined
          }
          onNextPhoto={
            photoDashboard.nextPhoto ? () => void photoDashboard.selectPhoto(photoDashboard.nextPhoto!) : undefined
          }
        />
      )}
      {pwaInstall.guideOpen && <PwaInstallGuide onClose={pwaInstall.closeGuide} />}
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
      <Routes>
        <Route
          path="/privacy"
          element={
            <div className="public-shell">
              <PrivacyPage theme={theme} onToggleTheme={onToggleTheme} />
              <AppFooter privacyCurrent />
            </div>
          }
        />
        <Route path="*" element={privateShell} />
      </Routes>
    </Suspense>
  )
}
