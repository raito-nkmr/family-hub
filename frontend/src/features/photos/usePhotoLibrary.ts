import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import i18n from '../../i18n'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { getGroups } from '../groups/api'
import {
  addBulkPhotoSharing,
  getPhoto,
  getPhotoTimeline,
  getStorageStatus,
  removePhotoGroupShareAsAdmin,
  setPhotoFavorite,
  trashPhoto,
  updatePhoto,
  type BulkSharingResult,
  type Photo,
  type PhotoFilters,
  type PhotoListItem,
  type PhotoPage,
} from './api'
import { readPhotoSearchParams, readTimelineYear, writePhotoSearchParams } from './photoSearchParams'
import { usePhotoList } from './usePhotoList'

const currentTimelineYear = Number(
  new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Tokyo', year: 'numeric' }).format(new Date()),
)

interface PhotoLibraryOptions {
  libraryEnabled: boolean
  storageEnabled: boolean
  onUnauthorized: () => void
}

export function usePhotoLibrary({ libraryEnabled, storageEnabled, onUnauthorized }: PhotoLibraryOptions) {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(null)
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [metadataError, setMetadataError] = useState<string | null>(null)
  const [updatingMetadata, setUpdatingMetadata] = useState(false)
  const photoFilters = readPhotoSearchParams(searchParams)
  const timelineYear = readTimelineYear(searchParams, currentTimelineYear)

  const storageQuery = useQuery({
    queryKey: queryKeys.photoStorage,
    queryFn: ({ signal }) => getStorageStatus(signal),
    enabled: storageEnabled,
  })
  const groupsQuery = useQuery({ queryKey: queryKeys.groups, queryFn: ({ signal }) => getGroups(signal) })
  const timelineQuery = useQuery({
    queryKey: queryKeys.photoTimeline(timelineYear),
    queryFn: ({ signal }) => getPhotoTimeline(timelineYear, signal),
    enabled: libraryEnabled,
  })
  const photoList = usePhotoList({ filters: photoFilters, enabled: libraryEnabled })
  const detailQuery = useQuery({
    queryKey: queryKeys.photo(selectedPhotoId ?? ''),
    queryFn: ({ signal }) => getPhoto(selectedPhotoId!, signal),
    enabled: selectedPhotoId !== null,
  })
  const unauthorizedCandidate = [
    storageQuery.error,
    groupsQuery.error,
    timelineQuery.error,
    photoList.error,
    detailQuery.error,
  ].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedCandidate, onUnauthorized)

  const selectedPhoto = detailQuery.data ?? null
  const invalidateLibrary = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.photosPrefix }),
      queryClient.invalidateQueries({ queryKey: queryKeys.photoTimelinePrefix }),
      queryClient.invalidateQueries({ queryKey: queryKeys.photoStorage }),
    ])
  }
  const search = async (filters: PhotoFilters) => {
    setPageMutationError(null)
    setSearchParams((current) => writePhotoSearchParams(current, filters), { replace: true })
  }
  const changeTimelineYear = async (year: number) => {
    if (year < 1 || year > 9998 || year === timelineYear) return
    setPageMutationError(null)
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('year', String(year))
        return next
      },
      { replace: true },
    )
  }
  const selectPhoto = async (photo: Photo | PhotoListItem) => {
    setSelectedPhotoId(photo.id)
    setMetadataError(null)
    try {
      await queryClient.fetchQuery({
        queryKey: queryKeys.photo(photo.id),
        queryFn: ({ signal }) => getPhoto(photo.id, signal),
      })
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setPageMutationError(i18n.t('photos.detailFailed'))
    }
  }
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
      await queryClient.invalidateQueries({ queryKey: queryKeys.photosPrefix })
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
  const bulkAddSharing = async (photoIds: string[], groupIds: string[]): Promise<BulkSharingResult> => {
    try {
      const result = await addBulkPhotoSharing(photoIds, groupIds)
      await queryClient.invalidateQueries({ queryKey: queryKeys.photosPrefix })
      return result
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      throw error
    }
  }
  const moveSelectedPhotoToTrash = async () => {
    if (!selectedPhoto) return
    setUpdatingMetadata(true)
    setMetadataError(null)
    try {
      await trashPhoto(selectedPhoto.id)
      removePhotoFromPages(queryClient, photoFilters, selectedPhoto.id)
      setSelectedPhotoId(null)
      await queryClient.invalidateQueries({ queryKey: queryKeys.photoTimelinePrefix })
    } catch (error) {
      if (isUnauthorizedError(error)) onUnauthorized()
      else setMetadataError(i18n.t('photoTrash.trashFailed'))
    } finally {
      setUpdatingMetadata(false)
    }
  }
  const queryError = [storageQuery.error, groupsQuery.error, timelineQuery.error, photoList.error].some(Boolean)
    ? i18n.t('photos.loadFailed')
    : null

  return {
    storage: storageQuery.data ?? null,
    photos: photoList.photos,
    photoFilters,
    totalCount: photoList.totalCount,
    timeline: timelineQuery.data ?? null,
    groups: groupsQuery.data ?? [],
    selectedPhoto,
    loading:
      groupsQuery.isPending ||
      (storageEnabled && storageQuery.isPending) ||
      (libraryEnabled && (timelineQuery.isPending || photoList.loading)),
    loadingMore: photoList.loadingMore,
    updatingMetadata,
    pageError: pageMutationError ?? queryError,
    metadataError,
    hasMore: photoList.hasMore,
    refresh: invalidateLibrary,
    search,
    loadMore: async () => {
      await photoList.loadMore()
    },
    changeTimelineYear,
    changeSharing,
    toggleFavorite,
    moderateGroupShare,
    savePhotoMetadata,
    bulkAddSharing,
    moveSelectedPhotoToTrash,
    selectPhoto,
    closePhoto: () => {
      setMetadataError(null)
      setSelectedPhotoId(null)
    },
    reportError: setPageMutationError,
    reset: () => {
      setSelectedPhotoId(null)
      setPageMutationError(null)
      setMetadataError(null)
      setUpdatingMetadata(false)
    },
    invalidateLibrary,
  }
}

function removePhotoFromPages(queryClient: ReturnType<typeof useQueryClient>, filters: PhotoFilters, photoId: string) {
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
