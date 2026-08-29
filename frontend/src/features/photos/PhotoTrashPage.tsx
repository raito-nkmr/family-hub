import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { isApiErrorWithStatus, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { formatDateTime } from '../../shared/lib/format'
import { Dialog } from '../../shared/ui/Dialog'
import { EmptyState } from '../../shared/ui/EmptyState'
import { InfiniteScrollTrigger } from '../../shared/ui/InfiniteScrollTrigger'
import { LoadingState } from '../../shared/ui/LoadingState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { useConfirmation } from '../../shared/ui/confirmation'
import { DeleteIcon, UndoIcon } from '../../shared/ui/icons'
import {
  getTrashedPhotos,
  getTrashedPhotoThumbnailUrl,
  permanentlyDeletePhoto,
  restorePhoto,
  type Photo,
  type TrashedPhotoList,
} from './api'
import { PhotoGridDensity } from './components/PhotoGridDensity'
import { usePhotoGridColumns } from './components/usePhotoGridColumns'

interface PhotoTrashPageProps {
  onUnauthorized: () => void
  onLibraryChanged: () => void
}

export function PhotoTrashPage({ onUnauthorized, onLibraryChanged }: PhotoTrashPageProps) {
  const { t } = useTranslation()
  const confirm = useConfirmation()
  const queryClient = useQueryClient()
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { gridColumns, changeGridColumns } = usePhotoGridColumns()
  const trashQuery = useInfiniteQuery({
    queryKey: queryKeys.photoTrash,
    queryFn: ({ pageParam, signal }) => getTrashedPhotos(signal, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  })
  const restoreMutation = useMutation({ mutationFn: restorePhoto })
  const deleteMutation = useMutation({ mutationFn: permanentlyDeletePhoto })
  const unauthorizedError = [trashQuery.error, restoreMutation.error, deleteMutation.error].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedError, onUnauthorized)
  const pages = trashQuery.data?.pages ?? []
  const photos = pages.flatMap((page) => page.items)
  const pendingId = restoreMutation.isPending
    ? restoreMutation.variables
    : deleteMutation.isPending
      ? deleteMutation.variables
      : null

  const restore = async (photo: Photo) => {
    setError(null)
    try {
      await restoreMutation.mutateAsync(photo.id)
      removePhotoFromTrashCache(queryClient, photo.id)
      setSelectedPhoto(null)
      onLibraryChanged()
    } catch (caught) {
      if (isUnauthorizedError(caught)) onUnauthorized()
      else setError(t('photoTrash.restoreFailed'))
    }
  }

  const deletePermanently = async (photo: Photo) => {
    if (!(await confirm(t('photoTrash.permanentConfirm', { filename: photo.original_filename })))) return
    setError(null)
    try {
      await deleteMutation.mutateAsync(photo.id)
      removePhotoFromTrashCache(queryClient, photo.id)
      setSelectedPhoto(null)
      onLibraryChanged()
    } catch (caught) {
      if (isUnauthorizedError(caught)) onUnauthorized()
      else if (isApiErrorWithStatus(caught, 409)) setError(t('photoTrash.deleteNotDue'))
      else setError(t('photoTrash.deleteFailed'))
    }
  }

  return (
    <main className="trash-page">
      <header className="page-heading">
        <div>
          <h1>{t('photoTrash.title')}</h1>
          <p>{t('photoTrash.description')}</p>
          {!trashQuery.isPending && (
            <p>{t('photoTrash.count', { shown: photos.length, total: pages[0]?.total_count ?? 0 })}</p>
          )}
        </div>
        <RefreshButton onClick={() => trashQuery.refetch()} disabled={trashQuery.isFetching} />
      </header>
      {error && <PageMessage>{error}</PageMessage>}
      {trashQuery.isPending ? (
        <LoadingState label={t('photoTrash.loading')} />
      ) : trashQuery.error && !isUnauthorizedError(trashQuery.error) ? (
        <PageMessage>{t('photoTrash.loadFailed')}</PageMessage>
      ) : photos.length === 0 ? (
        <EmptyState
          icon={<DeleteIcon />}
          title={t('photoTrash.empty')}
          description={t('photoTrash.emptyHelp')}
          titleAs="h2"
        />
      ) : (
        <>
          <PhotoGridDensity columns={gridColumns} onChange={changeGridColumns} />
          <div className={`photo-grid photo-grid--columns-${gridColumns}`}>
            {photos.map((photo) => (
              <button
                className="photo-card trash-photo-card"
                type="button"
                key={photo.id}
                aria-label={t('photoTrash.openPhoto', { filename: photo.original_filename })}
                onClick={() => setSelectedPhoto(photo)}
              >
                <div className="photo-card__image-wrap">
                  <img className="photo-card__image" src={getTrashedPhotoThumbnailUrl(photo.id)} alt="" />
                  {photo.lifecycle_state === 'purge_pending' && (
                    <span className="trash-photo-card__status">{t('photoTrash.pending')}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
          <InfiniteScrollTrigger
            hasMore={trashQuery.hasNextPage}
            loading={trashQuery.isFetchingNextPage}
            autoLoad={!trashQuery.isFetchNextPageError}
            onLoadMore={() => void trashQuery.fetchNextPage()}
          />
        </>
      )}
      {selectedPhoto && (
        <Dialog
          titleId="trash-photo-dialog-title"
          className="trash-photo-dialog"
          size="medium"
          surface="media"
          busy={pendingId === selectedPhoto.id}
          onClose={() => setSelectedPhoto(null)}
        >
          <img src={getTrashedPhotoThumbnailUrl(selectedPhoto.id)} alt="" />
          <div className="trash-photo-dialog__body">
            <p className="eyebrow">{t('photoTrash.detailEyebrow')}</p>
            <h2 id="trash-photo-dialog-title">{selectedPhoto.original_filename}</h2>
            <p>{t('photoTrash.trashedAt', { date: formatDateTime(selectedPhoto.trashed_at!) })}</p>
            <p>{t('photoTrash.purgeEligibleAt', { date: formatDateTime(selectedPhoto.purge_after!) })}</p>
            {selectedPhoto.lifecycle_state === 'purge_pending' ? (
              <PageMessage variant="neutral">{t('photoTrash.purgePending')}</PageMessage>
            ) : (
              <div className="trash-photo-dialog__actions">
                <button
                  className="secondary-button icon-button"
                  type="button"
                  disabled={pendingId === selectedPhoto.id}
                  onClick={() => void restore(selectedPhoto)}
                >
                  <UndoIcon />
                  {t('photoTrash.restore')}
                </button>
                <button
                  className="danger-button icon-button"
                  type="button"
                  disabled={pendingId === selectedPhoto.id || !isPurgeDue(selectedPhoto)}
                  onClick={() => void deletePermanently(selectedPhoto)}
                >
                  <DeleteIcon />
                  {t('photoTrash.deletePermanently')}
                </button>
              </div>
            )}
          </div>
        </Dialog>
      )}
    </main>
  )
}

function isPurgeDue(photo: Photo): boolean {
  return photo.purge_after !== null && Date.parse(photo.purge_after) <= Date.now()
}

function removePhotoFromTrashCache(queryClient: ReturnType<typeof useQueryClient>, photoId: string) {
  queryClient.setQueryData<InfiniteData<TrashedPhotoList>>(queryKeys.photoTrash, (current) =>
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
