import { useTranslation } from 'react-i18next'
import { useNotificationLocaleSync } from '../features/notifications/useNotificationLocaleSync'
import { usePhotoActivity } from '../features/photos/usePhotoActivity'
import { usePhotoDashboard } from '../features/photos/usePhotoDashboard'
import { usePwaInstallGuide } from '../features/pwa/usePwaInstallGuide'
import { isAppPhotoView } from './authenticatedAppStateHelpers'
import type { AppView } from './routes'
import { queryClient } from '../shared/api/queryClient'
import { usePullToRefresh } from '../shared/ui/usePullToRefresh'

interface UseAuthenticatedAppStateOptions {
  currentUserId: string
  activeView: AppView | null
  onUnauthorized: () => void
}

export function useAuthenticatedAppState({
  currentUserId,
  activeView,
  onUnauthorized,
}: UseAuthenticatedAppStateOptions) {
  const { i18n } = useTranslation()
  useNotificationLocaleSync({
    locale: i18n.resolvedLanguage === 'ja' ? 'ja' : 'en',
    onUnauthorized,
  })

  const photoDashboard = usePhotoDashboard({
    libraryEnabled: activeView === 'photos',
    storageEnabled: activeView !== null && isAppPhotoView(activeView),
    groupsEnabled: activeView === 'home' || activeView === 'photos' || activeView === 'albums',
    onUnauthorized,
  })
  const photoActivity = usePhotoActivity({
    userId: currentUserId,
    active: activeView === 'photo-activity',
    onUnauthorized,
  })
  const pwaInstall = usePwaInstallGuide()
  const pullToRefresh = usePullToRefresh({
    onRefresh: () => {
      if (queryClient.isMutating() > 0) return
      return queryClient.invalidateQueries()
    },
  })

  return { photoDashboard, photoActivity, pwaInstall, pullToRefresh }
}
