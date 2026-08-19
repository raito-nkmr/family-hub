import { useCallback } from 'react'
import { usePhotoLibrary } from './usePhotoLibrary'
import { usePhotoUpload } from './usePhotoUpload'

interface PhotoDashboardOptions {
  enabled: boolean
  libraryEnabled?: boolean
  storageEnabled?: boolean
  onUnauthorized: () => void
}

export function usePhotoDashboard({
  enabled,
  libraryEnabled = enabled,
  storageEnabled = enabled,
  onUnauthorized,
}: PhotoDashboardOptions) {
  const library = usePhotoLibrary({ libraryEnabled, storageEnabled, onUnauthorized })
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
    prepareForSession: reset,
    reset,
  }
}
