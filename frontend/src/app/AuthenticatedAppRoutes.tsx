import { lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import type { AuthUser } from '../features/auth/api'
import type { usePhotoActivity } from '../features/photos/usePhotoActivity'
import type { usePhotoDashboard } from '../features/photos/usePhotoDashboard'
import type { usePwaInstallGuide } from '../features/pwa/usePwaInstallGuide'
import { appPaths, type AppView } from './routes'
import { RequireAdmin } from './routeGuards'

const AccountPage = lazy(() =>
  import('../features/auth/AccountPage').then((module) => ({ default: module.AccountPage })),
)
const AlbumPage = lazy(() => import('../features/albums/AlbumPage').then((module) => ({ default: module.AlbumPage })))
const ChoresPage = lazy(() =>
  import('../features/chores/ChoresPage').then((module) => ({ default: module.ChoresPage })),
)
const ChoreDailyPage = lazy(() =>
  import('../features/chores/ChoreDailyPage').then((module) => ({ default: module.ChoreDailyPage })),
)
const ChoreMonthlyReportPage = lazy(() =>
  import('../features/chores/ChoreMonthlyReportPage').then((module) => ({ default: module.ChoreMonthlyReportPage })),
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

interface AuthenticatedAppRoutesProps {
  currentUser: AuthUser
  activeView: AppView | null
  onUnauthorized: () => void
  onCurrentUserChanged: (user: AuthUser) => void
  photoActivity: ReturnType<typeof usePhotoActivity>
  photoDashboard: ReturnType<typeof usePhotoDashboard>
  pwaInstall: ReturnType<typeof usePwaInstallGuide>
}

export function AuthenticatedAppRoutes({
  currentUser,
  activeView,
  onUnauthorized,
  onCurrentUserChanged,
  photoActivity,
  photoDashboard,
  pwaInstall,
}: AuthenticatedAppRoutesProps) {
  return (
    <Routes>
      <Route
        path={appPaths.home}
        element={
          <HomeRoute
            userId={currentUser.id}
            active={activeView === 'home'}
            onUnauthorized={onUnauthorized}
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
        element={<AlbumPage onUnauthorized={onUnauthorized} onSelectPhoto={photoDashboard.selectPhoto} />}
      />
      <Route
        path={appPaths['photo-trash']}
        element={
          <PhotoTrashPage onUnauthorized={onUnauthorized} onLibraryChanged={() => void photoDashboard.refresh()} />
        }
      />
      <Route path={appPaths.chores} element={<ChoresPage onUnauthorized={onUnauthorized} />} />
      <Route path={appPaths['chores-daily']} element={<ChoreDailyPage onUnauthorized={onUnauthorized} />} />
      <Route path={appPaths['chores-monthly']} element={<ChoreMonthlyReportPage onUnauthorized={onUnauthorized} />} />
      <Route path={appPaths.shopping} element={<ShoppingPage onUnauthorized={onUnauthorized} />} />
      <Route
        path={appPaths.groups}
        element={<GroupPage currentUserId={currentUser.id} onUnauthorized={onUnauthorized} />}
      />
      <Route
        path={appPaths.account}
        element={
          <AccountPage
            username={currentUser.username}
            onSessionEnded={onUnauthorized}
            showPwaInstallGuideEntry={pwaInstall.installGuideAvailable}
            onShowPwaInstallGuide={pwaInstall.openGuide}
          />
        }
      />
      <Route
        path={appPaths.invitations}
        element={
          <RequireAdmin role={currentUser.system_role}>
            <InvitationAdminPage onUnauthorized={onUnauthorized} />
          </RequireAdmin>
        }
      />
      <Route
        path={appPaths.system}
        element={
          <RequireAdmin role={currentUser.system_role}>
            <SystemStatusPage
              currentUserId={currentUser.id}
              onUnauthorized={onUnauthorized}
              onCurrentUserChanged={onCurrentUserChanged}
            />
          </RequireAdmin>
        }
      />
      <Route path="*" element={<Navigate to={appPaths.home} replace />} />
    </Routes>
  )
}
