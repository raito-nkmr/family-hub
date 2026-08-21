import { useCallback, useState } from 'react'
import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import {
  removePhotoGroupShareAsAdmin,
  setPhotoFavorite,
  trashPhoto,
  updatePhoto,
  type Photo,
  type PhotoFilters,
  type PhotoPage,
} from './api'

interface UsePhotoMetadataOptions {
  selectedPhoto: Photo | null
  photoFilters: PhotoFilters
  invalidateLibrary: () => Promise<void>
  onUnauthorized: () => void
  onSelectionCleared: () => void
}

export function usePhotoMetadata({
  selectedPhoto,
  photoFilters,
  invalidateLibrary,
  onUnauthorized,
  onSelectionCleared,
}: UsePhotoMetadataOptions) {
  const queryClient = useQueryClient()
  const [updatingMetadata, setUpdatingMetadata] = useState(false)
  const [metadataError, setMetadataError] = useState<string | null>(null)

  const clearError = useCallback(() => setMetadataError(null), [])
  const savePhotoMetadata = async (changes: {
    memo?: string | null
    sharing?: { type: 'private' | 'shared'; group_ids: string[] }
    captured_at_override?: string | null
  }) => {
    if (!selectedPhoto) return
    setUpdatingMetadata(true)
    setMetadataError(null)
    try {
      const updated = await updatePhoto(selectedPhoto.id, { ...changes, version: selectedPhoto.metadata_version })
      queryClient.setQueryData(queryKeys.photo(updated.id), updated)
      await invalidateLibrary()
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else
        setMetadataError(
          isApiErrorWithStatus(error, 409) ? i18n.t('photos.updateConflict') : i18n.t('photos.updateFailed'),
        )
    } finally {
      setUpdatingMetadata(false)
    }
  }

  const changeSharing = async (groupIds: string[]) => {
    if (!selectedPhoto) return
    const currentIds = selectedPhoto.sharing.group_ids ?? []
    if (currentIds.length === groupIds.length && currentIds.every((id) => groupIds.includes(id))) return
    await savePhotoMetadata({ sharing: { type: groupIds.length > 0 ? 'shared' : 'private', group_ids: groupIds } })
  }

  const toggleFavorite = async () => {
    if (!selectedPhoto) return
    setUpdatingMetadata(true)
    setMetadataError(null)
    try {
      const updated = await setPhotoFavorite(selectedPhoto.id, !selectedPhoto.is_favorite)
      queryClient.setQueryData(queryKeys.photo(updated.id), updated)
      await invalidateLibrary()
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setMetadataError(i18n.t('photos.updateFailed'))
    } finally {
      setUpdatingMetadata(false)
    }
  }

  const moderateGroupShare = async (groupId: string, currentPassword: string) => {
    if (!selectedPhoto) return
    setUpdatingMetadata(true)
    setMetadataError(null)
    try {
      const updated = await removePhotoGroupShareAsAdmin(selectedPhoto.id, groupId, currentPassword)
      queryClient.setQueryData(queryKeys.photo(updated.id), updated)
      await invalidateLibrary()
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setMetadataError(i18n.t('photos.updateFailed'))
    } finally {
      setUpdatingMetadata(false)
    }
  }

  const moveSelectedPhotoToTrash = async () => {
    if (!selectedPhoto) return
    setUpdatingMetadata(true)
    setMetadataError(null)
    try {
      await trashPhoto(selectedPhoto.id)
      removePhotoFromPages(queryClient, photoFilters, selectedPhoto.id)
      onSelectionCleared()
      await invalidateLibrary()
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setMetadataError(i18n.t('photoTrash.trashFailed'))
    } finally {
      setUpdatingMetadata(false)
    }
  }

  const reset = useCallback(() => {
    setMetadataError(null)
    setUpdatingMetadata(false)
  }, [])

  return {
    updatingMetadata,
    metadataError,
    clearError,
    reset,
    changeSharing,
    toggleFavorite,
    moderateGroupShare,
    savePhotoMetadata,
    moveSelectedPhotoToTrash,
  }
}

function removePhotoFromPages(queryClient: QueryClient, filters: PhotoFilters, photoId: string) {
  queryClient.setQueryData<{ pages: PhotoPage[]; pageParams: unknown[] }>(queryKeys.photos(filters), (current) =>
    current
      ? {
          ...current,
          pages: current.pages.map((page) => ({
            ...page,
            items: page.items.filter((photo) => photo.id !== photoId),
            total_count: Math.max(0, page.total_count - 1),
          })),
        }
      : current,
  )
}
