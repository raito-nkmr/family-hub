import { useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { isUnauthorizedError } from '../../../shared/api/errors'
import { formatDateTime } from '../../../shared/lib/format'
import { Dialog } from '../../../shared/ui/Dialog'
import { DialogActions } from '../../../shared/ui/DialogActions'
import { LoadingState } from '../../../shared/ui/LoadingState'
import { AddPhotoIcon } from '../../../shared/ui/icons'
import { InfiniteScrollTrigger } from '../../../shared/ui/InfiniteScrollTrigger'
import { useUnauthorizedError } from '../../../shared/api/useUnauthorizedError'
import type { PhotoFilters, PhotoSearchOptions } from '../../photos/api'
import { PhotoPreview } from '../../photos/public'
import { PhotoSearchPanel } from '../../photos/components/PhotoSearchPanel'
import { usePhotoList } from '../../photos/usePhotoList'

interface PhotoPickerDialogProps {
  albumId: string
  groupId: string
  searchOptions?: PhotoSearchOptions | null
  searchOptionsLoading?: boolean
  submitting: boolean
  error: string | null
  onUnauthorized: () => void
  onSubmit: (photoIds: string[]) => Promise<void>
  onClose: () => void
}

export function PhotoPickerDialog({
  albumId,
  groupId,
  searchOptions = null,
  searchOptionsLoading = false,
  submitting,
  error,
  onUnauthorized,
  onSubmit,
  onClose,
}: PhotoPickerDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const [searchFilters, setSearchFilters] = useState<PhotoFilters>({})
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const photoList = usePhotoList({ filters: { ...searchFilters, excludeAlbumId: albumId, sharingGroupId: groupId } })
  useUnauthorizedError(photoList.error, onUnauthorized)
  const listError =
    photoList.error && !isUnauthorizedError(photoList.error)
      ? t(photoList.loadMoreFailed ? 'photos.moreFailed' : 'photos.loadFailed')
      : null
  const selectedCount = selectedIds.size
  const selectedArray = useMemo(() => [...selectedIds], [selectedIds])

  const search = (nextFilters: PhotoFilters) => {
    setSearchFilters(nextFilters)
  }

  const togglePhoto = (photoId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(photoId)) next.delete(photoId)
      else if (next.size < 200) next.add(photoId)
      return next
    })
  }

  return (
    <Dialog titleId={headingId} className="photo-picker-dialog" size="extra-large" busy={submitting} onClose={onClose}>
      <div className="dialog__heading photo-picker-dialog__heading">
        <div>
          <h2 id={headingId}>{t('albums.addPhotos')}</h2>
          <small>{t('albums.loadedCount', { total: photoList.totalCount, shown: photoList.photos.length })}</small>
        </div>
        <span>{t('albums.selectedCount', { count: selectedCount })}</span>
      </div>

      <PhotoSearchPanel
        filters={searchFilters}
        searchOptions={searchOptions}
        searchOptionsLoading={searchOptionsLoading}
        showSharingGroupFilter={false}
        timeline={null}
        disabled={photoList.loading}
        onSearch={search}
      />

      {photoList.loading ? (
        <LoadingState label={t('photos.loadingList')} />
      ) : photoList.photos.length > 0 ? (
        <div className="photo-picker-grid">
          {photoList.photos.map((photo) => {
            const selected = selectedIds.has(photo.id)
            return (
              <button
                className={selected ? 'photo-picker-item photo-picker-item--selected' : 'photo-picker-item'}
                type="button"
                key={photo.id}
                aria-pressed={selected}
                onClick={() => togglePhoto(photo.id)}
              >
                <div className="photo-picker-item__image-wrap">
                  <PhotoPreview photo={photo} className="photo-picker-item__image" />
                  <span className="photo-picker-item__check">{selected ? '✓' : ''}</span>
                </div>
                <span className="photo-picker-item__name">{photo.original_filename}</span>
                <span className="photo-picker-item__date">
                  {photo.captured_at ? formatDateTime(photo.captured_at) : t('photos.capturedUnknown')}
                </span>
              </button>
            )
          })}
        </div>
      ) : (
        <div className="dialog-empty-state">
          <p>{t('albums.noAvailable')}</p>
          <span>{t('albums.noAvailableHelp')}</span>
        </div>
      )}

      <InfiniteScrollTrigger
        hasMore={photoList.hasMore}
        loading={photoList.loadingMore}
        autoLoad={!listError}
        onLoadMore={() => void photoList.loadMore()}
      />
      {(error || listError) && (
        <p className="dialog-error" role="alert">
          {error || listError}
        </p>
      )}
      <DialogActions disabled={submitting} onCancel={onClose}>
        <button
          className="primary-button icon-button"
          type="button"
          disabled={submitting || selectedCount === 0}
          onClick={() => void onSubmit(selectedArray)}
        >
          <AddPhotoIcon />
          {submitting ? t('albums.adding') : t('albums.addSelected', { count: selectedCount })}
        </button>
      </DialogActions>
    </Dialog>
  )
}
