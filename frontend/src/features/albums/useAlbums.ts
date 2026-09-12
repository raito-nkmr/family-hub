import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { useSearchSelection } from '../../shared/routing/useSearchSelection'
import { useConfirmation } from '../../shared/ui/confirmation'
import { getGroups } from '../groups/api'
import type { Photo } from '../photos/public'
import { getPhotoSearchOptions } from '../photos/api'
import {
  addPhotosToAlbum,
  createAlbum,
  deleteAlbum,
  getAlbum,
  getAlbums,
  removePhotoFromAlbum,
  updateAlbum,
  type Album,
  type AlbumDetail,
} from './api'
import { getAlbumErrorMessage } from './errors'

interface UseAlbumsOptions {
  onUnauthorized: () => void
}

interface AlbumInput {
  title: string
  description: string | null
  group_ids: string[]
}

export function useAlbums({ onUnauthorized }: UseAlbumsOptions) {
  const queryClient = useQueryClient()
  const confirm = useConfirmation()
  const [selectedAlbumId, setSelectedAlbumId] = useSearchSelection('album')
  const [pageMutationError, setPageMutationError] = useState<string | null>(null)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [showPhotoPicker, setShowPhotoPicker] = useState(false)
  const [removingPhotoIds, setRemovingPhotoIds] = useState<Set<string>>(() => new Set())

  const albumsQuery = useQuery({ queryKey: queryKeys.albums, queryFn: ({ signal }) => getAlbums(signal) })
  const groupsQuery = useQuery({ queryKey: queryKeys.groups, queryFn: ({ signal }) => getGroups(signal) })
  const searchOptionsQuery = useQuery({
    queryKey: queryKeys.photoSearchOptions,
    queryFn: ({ signal }) => getPhotoSearchOptions(signal),
  })
  const detailQuery = useInfiniteQuery({
    queryKey: queryKeys.album(selectedAlbumId ?? ''),
    queryFn: ({ pageParam, signal }) => getAlbum(selectedAlbumId!, signal, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: selectedAlbumId !== null,
  })
  useUnauthorizedError(albumsQuery.error, onUnauthorized)
  useUnauthorizedError(groupsQuery.error, onUnauthorized)
  useUnauthorizedError(searchOptionsQuery.error, onUnauthorized)
  useUnauthorizedError(detailQuery.error, onUnauthorized)

  const createMutation = useMutation({
    mutationFn: createAlbum,
    onSuccess: (created) => {
      queryClient.setQueryData<Album[]>(queryKeys.albums, (current = []) => [created, ...current])
      setShowCreateDialog(false)
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({ albumId, value }: { albumId: string; value: Partial<AlbumInput> & { cover_photo_id?: string } }) =>
      updateAlbum(albumId, value),
    onSuccess: (updated) => updateAlbumCaches(queryClient, updated),
  })
  const addPhotosMutation = useMutation({
    mutationFn: ({ albumId, photoIds }: { albumId: string; photoIds: string[] }) => addPhotosToAlbum(albumId, photoIds),
    onSuccess: (updated) => replaceAlbumDetailCache(queryClient, updated),
  })

  const detailPages = detailQuery.data?.pages ?? []
  const selectedAlbum = detailPages[0]
    ? {
        ...detailPages[0],
        photos: detailPages.flatMap((page) => page.photos),
        next_cursor: detailPages.at(-1)?.next_cursor ?? null,
      }
    : null

  const openAlbum = async (album: Album) => {
    setSelectedAlbumId(album.id)
    setPageMutationError(null)
    try {
      await queryClient.fetchInfiniteQuery({
        queryKey: queryKeys.album(album.id),
        queryFn: ({ pageParam, signal }) => getAlbum(album.id, signal, pageParam),
        initialPageParam: undefined as string | undefined,
        getNextPageParam: (page: AlbumDetail) => page.next_cursor ?? undefined,
      })
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumDetail'), onUnauthorized, setPageMutationError)
    }
  }

  const refresh = async () => {
    setPageMutationError(null)
    await Promise.all([albumsQuery.refetch(), groupsQuery.refetch()])
  }

  const create = async (value: AlbumInput) => {
    setDialogError(null)
    try {
      await createMutation.mutateAsync(value)
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumCreate'), onUnauthorized, setDialogError)
    }
  }

  const update = async (value: AlbumInput) => {
    if (!selectedAlbumId) return
    setDialogError(null)
    try {
      await updateMutation.mutateAsync({
        albumId: selectedAlbumId,
        value: { title: value.title, description: value.description, group_ids: value.group_ids },
      })
      setShowEditDialog(false)
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumUpdate'), onUnauthorized, setDialogError)
    }
  }

  const remove = async () => {
    if (!selectedAlbum || !(await confirm(i18n.t('errors.albumDeleteConfirm', { title: selectedAlbum.title })))) return
    setPageMutationError(null)
    try {
      await deleteAlbum(selectedAlbum.id)
      queryClient.setQueryData<Album[]>(queryKeys.albums, (current = []) =>
        current.filter((album) => album.id !== selectedAlbum.id),
      )
      queryClient.removeQueries({ queryKey: queryKeys.album(selectedAlbum.id) })
      setSelectedAlbumId(null)
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumDelete'), onUnauthorized, setPageMutationError)
    }
  }

  const addPhotos = async (photoIds: string[]) => {
    if (!selectedAlbumId) return
    setDialogError(null)
    try {
      await addPhotosMutation.mutateAsync({ albumId: selectedAlbumId, photoIds })
      setShowPhotoPicker(false)
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumAdd'), onUnauthorized, setDialogError)
    }
  }

  const removePhotos = async (photoIds: string[]): Promise<boolean> => {
    if (!selectedAlbumId || photoIds.length === 0) return false
    if (!(await confirm(i18n.t('albums.removeConfirm', { count: photoIds.length })))) return false
    setRemovingPhotoIds(new Set(photoIds))
    setPageMutationError(null)
    try {
      const results = await Promise.allSettled(
        photoIds.map((photoId) => removePhotoFromAlbum(selectedAlbumId, photoId)),
      )
      const updatedAlbums = await getAlbums()
      queryClient.setQueryData(queryKeys.albums, updatedAlbums)
      await queryClient.invalidateQueries({ queryKey: queryKeys.album(selectedAlbumId) })
      const failure = results.find((result): result is PromiseRejectedResult => result.status === 'rejected')
      if (failure) {
        handleAlbumError(failure.reason, i18n.t('errors.albumRemove'), onUnauthorized, setPageMutationError)
        return false
      }
      return true
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumRemove'), onUnauthorized, setPageMutationError)
      return false
    } finally {
      setRemovingPhotoIds(new Set())
    }
  }

  const setCover = async (photo: Photo): Promise<boolean> => {
    if (!selectedAlbumId) return false
    setPageMutationError(null)
    try {
      await updateMutation.mutateAsync({ albumId: selectedAlbumId, value: { cover_photo_id: photo.id } })
      return true
    } catch (error) {
      handleAlbumError(error, i18n.t('errors.albumUpdate'), onUnauthorized, setPageMutationError)
      return false
    }
  }

  const openDialog = (dialog: 'create' | 'edit' | 'photos') => {
    setDialogError(null)
    if (dialog === 'create') setShowCreateDialog(true)
    if (dialog === 'edit') setShowEditDialog(true)
    if (dialog === 'photos') setShowPhotoPicker(true)
  }
  const queryError =
    albumsQuery.error || groupsQuery.error
      ? i18n.t('errors.albumLoad')
      : detailQuery.error
        ? i18n.t('errors.albumDetail')
        : null

  return {
    albums: albumsQuery.data ?? [],
    groups: groupsQuery.data ?? [],
    searchOptions: searchOptionsQuery.data ?? null,
    searchOptionsLoading: searchOptionsQuery.isPending,
    selectedAlbum,
    loading: albumsQuery.isPending || groupsQuery.isPending,
    detailLoading: selectedAlbumId !== null && detailQuery.isPending,
    pageError: pageMutationError ?? queryError,
    dialogError,
    showCreateDialog,
    showEditDialog,
    showPhotoPicker,
    submitting: createMutation.isPending || updateMutation.isPending || addPhotosMutation.isPending,
    removingPhotoIds,
    openAlbum,
    refresh,
    create,
    update,
    remove,
    addPhotos,
    removePhotos,
    setCover,
    loadMore: async () => {
      if (detailQuery.hasNextPage && !detailQuery.isFetchingNextPage) await detailQuery.fetchNextPage()
    },
    loadingMore: detailQuery.isFetchingNextPage,
    hasMore: Boolean(detailQuery.hasNextPage),
    loadMoreFailed: detailQuery.isFetchNextPageError,
    backToList: () => setSelectedAlbumId(null),
    openDialog,
    closeCreateDialog: () => setShowCreateDialog(false),
    closeEditDialog: () => setShowEditDialog(false),
    closePhotoPicker: () => setShowPhotoPicker(false),
  }
}

function updateAlbumCaches(queryClient: ReturnType<typeof useQueryClient>, updated: Album | AlbumDetail) {
  queryClient.setQueryData<Album[]>(queryKeys.albums, (current = []) => [
    updated,
    ...current.filter((album) => album.id !== updated.id),
  ])
  queryClient.setQueryData<InfiniteData<AlbumDetail>>(queryKeys.album(updated.id), (current) =>
    current
      ? {
          ...current,
          pages: current.pages.map((page) => ({
            ...page,
            ...updated,
            photos: 'photos' in updated ? updated.photos : page.photos,
            next_cursor: 'photos' in updated ? updated.next_cursor : page.next_cursor,
          })),
        }
      : 'photos' in updated
        ? { pages: [updated], pageParams: [undefined] }
        : current,
  )
}

function replaceAlbumDetailCache(queryClient: ReturnType<typeof useQueryClient>, updated: AlbumDetail) {
  queryClient.setQueryData<Album[]>(queryKeys.albums, (current = []) => [
    updated,
    ...current.filter((album) => album.id !== updated.id),
  ])
  queryClient.setQueryData<InfiniteData<AlbumDetail>>(queryKeys.album(updated.id), {
    pages: [updated],
    pageParams: [undefined],
  })
}

function handleAlbumError(
  error: unknown,
  fallback: string,
  onUnauthorized: () => void,
  setError: (message: string) => void,
) {
  if (isUnauthorizedError(error)) onUnauthorized()
  else setError(getAlbumErrorMessage(error, fallback))
}
