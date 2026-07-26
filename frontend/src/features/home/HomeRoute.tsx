import { HomePage } from './HomePage'
import { useHome } from './useHome'
import type { usePhotoActivity } from '../photos/usePhotoActivity'
import type { usePhotoDashboard } from '../photos/usePhotoDashboard'
import type { usePwaInstallGuide } from '../pwa/usePwaInstallGuide'

interface HomeRouteProps {
  userId: string
  active: boolean
  onUnauthorized: () => void
  photoActivity: ReturnType<typeof usePhotoActivity>
  photoDashboard: ReturnType<typeof usePhotoDashboard>
  pwaInstall: ReturnType<typeof usePwaInstallGuide>
}

export function HomeRoute({
  userId,
  active,
  onUnauthorized,
  photoActivity,
  photoDashboard,
  pwaInstall,
}: HomeRouteProps) {
  const home = useHome({ userId, active, onUnauthorized })
  return (
    <HomePage
      recentPhotos={home.recentPhotos}
      unseenPhotoCount={photoActivity.unseenCount}
      groups={home.groups}
      cleaningTasks={home.cleaningTasks}
      shoppingItems={home.shoppingItems}
      loading={home.loading}
      error={home.error}
      onRefresh={() => void Promise.all([home.refresh(), photoActivity.refresh()])}
      onSelectPhoto={photoDashboard.selectPhoto}
      showPwaInstallPrompt={pwaInstall.homePromptVisible}
      onShowPwaInstallGuide={pwaInstall.openGuide}
      onDismissPwaInstallPrompt={pwaInstall.dismissHomePrompt}
    />
  )
}
