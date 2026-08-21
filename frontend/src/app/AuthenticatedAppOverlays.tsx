import type { usePhotoDashboard } from '../features/photos/usePhotoDashboard'
import { PhotoModal } from '../features/photos/components/PhotoModal'
import { PwaInstallGuide } from '../features/pwa/PwaInstallGuide'
import type { usePwaInstallGuide } from '../features/pwa/usePwaInstallGuide'

interface AuthenticatedAppOverlaysProps {
  currentUserId: string
  photoDashboard: ReturnType<typeof usePhotoDashboard>
  pwaInstall: ReturnType<typeof usePwaInstallGuide>
}

export function AuthenticatedAppOverlays({ currentUserId, photoDashboard, pwaInstall }: AuthenticatedAppOverlaysProps) {
  return (
    <>
      {(photoDashboard.selectedPhoto || photoDashboard.selectedPhotoSummary) && (
        <PhotoModal
          key={(photoDashboard.selectedPhoto ?? photoDashboard.selectedPhotoSummary)!.id}
          photo={photoDashboard.selectedPhoto ?? photoDashboard.selectedPhotoSummary!}
          photoDetailLoading={photoDashboard.photoDetailLoading}
          photoDetailError={photoDashboard.photoDetailError}
          currentUserId={currentUserId}
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
    </>
  )
}
