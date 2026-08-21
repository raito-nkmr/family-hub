import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { getGroups } from '../groups/api'
import { getPhotoSearchOptions, getPhotoTimeline, getStorageStatus, type PhotoFilters } from './api'
import { readPhotoSearchParams, readTimelineYear, writePhotoSearchParams } from './photoSearchParams'
import { usePhotoList } from './usePhotoList'

const currentTimelineYear = Number(
  new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Tokyo', year: 'numeric' }).format(new Date()),
)

interface PhotoLibraryDataOptions {
  libraryEnabled: boolean
  storageEnabled: boolean
  groupsEnabled: boolean
  onUnauthorized: () => void
}

export function usePhotoLibraryData({
  libraryEnabled,
  storageEnabled,
  groupsEnabled,
  onUnauthorized,
}: PhotoLibraryDataOptions) {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const photoFilters = readPhotoSearchParams(searchParams)
  const timelineYear = readTimelineYear(searchParams, currentTimelineYear)

  const storageQuery = useQuery({
    queryKey: queryKeys.photoStorage,
    queryFn: ({ signal }) => getStorageStatus(signal),
    enabled: storageEnabled,
  })
  const groupsQuery = useQuery({
    queryKey: queryKeys.groups,
    queryFn: ({ signal }) => getGroups(signal),
    enabled: groupsEnabled,
  })
  const searchOptionsQuery = useQuery({
    queryKey: queryKeys.photoSearchOptions,
    queryFn: ({ signal }) => getPhotoSearchOptions(signal),
    enabled: libraryEnabled,
  })
  const timelineQuery = useQuery({
    queryKey: queryKeys.photoTimeline(timelineYear),
    queryFn: ({ signal }) => getPhotoTimeline(timelineYear, signal),
    enabled: libraryEnabled,
  })
  const photoList = usePhotoList({ filters: photoFilters, enabled: libraryEnabled })
  const unauthorizedCandidate = [
    storageQuery.error,
    groupsQuery.error,
    timelineQuery.error,
    photoList.error,
    searchOptionsQuery.error,
  ].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedCandidate, onUnauthorized)

  const invalidateLibrary = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.photosPrefix }),
      queryClient.invalidateQueries({ queryKey: queryKeys.photoTimelinePrefix }),
      queryClient.invalidateQueries({ queryKey: queryKeys.photoStorage }),
      queryClient.invalidateQueries({ queryKey: queryKeys.recentPhotos }),
      queryClient.invalidateQueries({ queryKey: queryKeys.photoSearchOptions }),
    ])
  }, [queryClient])

  const search = async (filters: PhotoFilters) => {
    setSearchParams((current) => writePhotoSearchParams(current, filters), { replace: true })
  }

  const changeTimelineYear = async (year: number) => {
    if (year < 1 || year > 9998 || year === timelineYear) return
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current)
        next.set('year', String(year))
        return next
      },
      { replace: true },
    )
  }

  const queryError = [
    storageQuery.error,
    groupsQuery.error,
    timelineQuery.error,
    photoList.error,
    searchOptionsQuery.error,
  ].some(Boolean)
    ? i18n.t('photos.loadFailed')
    : null

  return {
    storage: storageQuery.data ?? null,
    photos: photoList.photos,
    photoFilters,
    totalCount: photoList.totalCount,
    timeline: timelineQuery.data ?? null,
    groups: groupsQuery.data ?? [],
    searchOptions: searchOptionsQuery.data ?? null,
    searchOptionsLoading: searchOptionsQuery.isPending,
    loading:
      (groupsEnabled && groupsQuery.isPending) ||
      (storageEnabled && storageQuery.isPending) ||
      (libraryEnabled && (timelineQuery.isPending || photoList.loading)),
    loadingMore: photoList.loadingMore,
    queryError,
    hasMore: photoList.hasMore,
    refresh: invalidateLibrary,
    search,
    loadMore: async () => {
      await photoList.loadMore()
    },
    changeTimelineYear,
    invalidateLibrary,
  }
}
