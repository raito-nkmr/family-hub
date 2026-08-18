import { useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { formatDateTime } from '../../shared/lib/format'
import { Dialog } from '../../shared/ui/Dialog'
import { InfiniteScrollTrigger } from '../../shared/ui/InfiniteScrollTrigger'
import { useConfirmation } from '../../shared/ui/confirmation'
import { DeleteIcon, RefreshIcon, UndoIcon } from '../../shared/ui/icons'
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
    } catch (caught) {
      if (isUnauthorizedError(caught)) onUnauthorized()
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
        <button
          className="refresh-button"
          type="button"
          onClick={() => void trashQuery.refetch()}
          disabled={trashQuery.isFetching}
        >
          <RefreshIcon />
          {t('common.refresh')}
        </button>
      </header>
      {error && (
        <div className="page-message page-message--error" role="alert">
          {error}
        </div>
      )}
      {trashQuery.isPending ? (
        <div className="feature-loading" aria-label={t('photoTrash.loading')}>
          <span className="spinner" />
        </div>
      ) : trashQuery.error && !isUnauthorizedError(trashQuery.error) ? (
        <div className="page-message page-message--error" role="alert">
          {t('photoTrash.loadFailed')}
        </div>
      ) : photos.length === 0 ? (
        <div className="empty-state">
          <span>
            <DeleteIcon />
          </span>
          <h2>{t('photoTrash.empty')}</h2>
          <p>{t('photoTrash.emptyHelp')}</p>
        </div>
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
            <p>{t('photoTrash.deletedAt', { date: formatDateTime(selectedPhoto.trashed_at!) })}</p>
            <p>{t('photoTrash.purgeAfter', { date: formatDateTime(selectedPhoto.purge_after!) })}</p>
            {selectedPhoto.lifecycle_state === 'purge_pending' ? (
              <p className="page-message">{t('photoTrash.purgePending')}</p>
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
                  disabled={pendingId === selectedPhoto.id}
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
