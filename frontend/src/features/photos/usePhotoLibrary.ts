import { useCallback, useState } from 'react'
import { isUnauthorizedError } from '../../shared/api/errors'
import { addBulkPhotoSharing, type BulkSharingResult } from './api'
import { usePhotoLibraryData } from './usePhotoLibraryData'
import { usePhotoMetadata } from './usePhotoMetadata'
import { usePhotoSelection } from './usePhotoSelection'

interface PhotoLibraryOptions {
  libraryEnabled: boolean
  storageEnabled: boolean
  groupsEnabled: boolean
  onUnauthorized: () => void
}

export function usePhotoLibrary({
  libraryEnabled,
  storageEnabled,
  groupsEnabled,
  onUnauthorized,
}: PhotoLibraryOptions) {
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const data = usePhotoLibraryData({ libraryEnabled, storageEnabled, groupsEnabled, onUnauthorized })
  const { invalidateLibrary } = data

  const selection = usePhotoSelection({ photos: data.photos, onUnauthorized })
  const {
    selectedPhoto,
    selectedPhotoSummary,
    photoDetailLoading,
    photoDetailError,
    photoDetailPageError,
    retryPhotoDetail,
    previousPhoto,
    nextPhoto,
    selectPhoto: selectSelectedPhoto,
    closePhoto: closeSelectedPhoto,
    reset: resetSelection,
  } = selection
  const metadata = usePhotoMetadata({
    selectedPhoto,
    photoFilters: data.photoFilters,
    invalidateLibrary: data.invalidateLibrary,
    onUnauthorized,
    onSelectionCleared: closeSelectedPhoto,
  })
  const { updatingMetadata, metadataError, clearError: clearMetadataError, reset: resetMetadata } = metadata
  const selectPhoto = async (photo: Parameters<typeof selection.selectPhoto>[0]) => {
    setPageMutationError(null)
    clearMetadataError()
    await selectSelectedPhoto(photo)
  }
  const search = async (filters: Parameters<typeof data.search>[0]) => {
    setPageMutationError(null)
    await data.search(filters)
  }
  const changeTimelineYear = async (year: number) => {
    setPageMutationError(null)
    await data.changeTimelineYear(year)
  }
  const bulkAddSharing = async (photoIds: string[], groupIds: string[]): Promise<BulkSharingResult> => {
    try {
      const result = await addBulkPhotoSharing(photoIds, groupIds)
      await invalidateLibrary()
      return result
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      throw error
    }
  }
  return {
    storage: data.storage,
    photos: data.photos,
    photoFilters: data.photoFilters,
    totalCount: data.totalCount,
    timeline: data.timeline,
    groups: data.groups,
    searchOptions: data.searchOptions,
    searchOptionsLoading: data.searchOptionsLoading,
    selectedPhoto,
    selectedPhotoSummary,
    photoDetailLoading,
    photoDetailError,
    retryPhotoDetail,
    previousPhoto,
    nextPhoto,
    loading: data.loading,
    loadingMore: data.loadingMore,
    updatingMetadata,
    pageError: photoDetailPageError ?? pageMutationError ?? data.queryError,
    metadataError,
    hasMore: data.hasMore,
    refresh: data.refresh,
    search,
    loadMore: data.loadMore,
    changeTimelineYear,
    changeSharing: metadata.changeSharing,
    toggleFavorite: metadata.toggleFavorite,
    moderateGroupShare: metadata.moderateGroupShare,
    savePhotoMetadata: metadata.savePhotoMetadata,
    bulkAddSharing,
    moveSelectedPhotoToTrash: metadata.moveSelectedPhotoToTrash,
    selectPhoto,
    closePhoto: useCallback(() => {
      clearMetadataError()
      closeSelectedPhoto()
      setPageMutationError(null)
    }, [clearMetadataError, closeSelectedPhoto]),
    reportError: setPageMutationError,
    reset: useCallback(() => {
      resetSelection()
      resetMetadata()
      setPageMutationError(null)
    }, [resetMetadata, resetSelection]),
    invalidateLibrary,
  }
}
