import { useCallback } from 'react'
import { usePhotoLibrary } from './usePhotoLibrary'
import { usePhotoUpload } from './usePhotoUpload'

interface PhotoDashboardOptions {
  libraryEnabled?: boolean
  storageEnabled?: boolean
  groupsEnabled?: boolean
  onUnauthorized: () => void
}

export function usePhotoDashboard({
  libraryEnabled = true,
  storageEnabled = true,
  groupsEnabled = libraryEnabled || storageEnabled,
  onUnauthorized,
}: PhotoDashboardOptions) {
  const library = usePhotoLibrary({ libraryEnabled, storageEnabled, groupsEnabled, onUnauthorized })
  const invalidateLibrary = library.invalidateLibrary
  const handleUploaded = useCallback(() => invalidateLibrary(), [invalidateLibrary])
  const upload = usePhotoUpload({ storage: library.storage, onUploaded: handleUploaded, onUnauthorized })
  const resetLibrary = library.reset
  const resetUpload = upload.reset
  const reset = useCallback(() => {
    resetLibrary()
    resetUpload()
  }, [resetLibrary, resetUpload])

  return {
    ...library,
    ...upload,
    reset,
  }
}
