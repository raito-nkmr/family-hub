import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { isAbortError, isUnauthorizedError } from '../../../shared/api/errors'
import { formatDateTime } from '../../../shared/lib/format'
import { Dialog } from '../../../shared/ui/Dialog'
import { AddPhotoIcon, CancelIcon } from '../../../shared/ui/icons'
import { InfiniteScrollTrigger } from '../../../shared/ui/InfiniteScrollTrigger'
import { getPhotos, type PhotoFilters, type PhotoListItem } from '../../photos/api'
import { PhotoPreview } from '../../photos/public'
import { PhotoSearchPanel } from '../../photos/components/PhotoSearchPanel'

interface PhotoPickerDialogProps {
  albumId: string
  groupId: string
  submitting: boolean
  error: string | null
  onUnauthorized: () => void
  onSubmit: (photoIds: string[]) => Promise<void>
  onClose: () => void
}

export function PhotoPickerDialog({
  albumId,
  groupId,
  submitting,
  error,
  onUnauthorized,
  onSubmit,
  onClose,
}: PhotoPickerDialogProps) {
  const { t, i18n } = useTranslation()
  const headingId = useId()
  const [photos, setPhotos] = useState<PhotoListItem[]>([])
  const [filters, setFilters] = useState<PhotoFilters>({
    excludeAlbumId: albumId,
    sharingGroupId: groupId,
  })
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const requestGenerationRef = useRef(0)
  const loadingMoreRef = useRef(false)
  const selectedCount = selectedIds.size
  const selectedArray = useMemo(() => [...selectedIds], [selectedIds])

  useEffect(() => {
    const generation = ++requestGenerationRef.current
    loadingMoreRef.current = false
    const controller = new AbortController()
    const load = async () => {
      try {
        const page = await getPhotos({ excludeAlbumId: albumId, sharingGroupId: groupId }, undefined, controller.signal)
        if (generation !== requestGenerationRef.current) return
        setPhotos(page.items)
        setNextCursor(page.next_cursor)
        setTotalCount(page.total_count)
      } catch (loadFailure) {
        if (isAbortError(loadFailure)) return
        if (isUnauthorizedError(loadFailure)) onUnauthorized()
        else setLoadError(i18n.t('photos.loadFailed'))
      } finally {
        if (generation === requestGenerationRef.current) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [albumId, groupId, i18n, onUnauthorized])

  const search = async (nextFilters: PhotoFilters) => {
    const generation = ++requestGenerationRef.current
    loadingMoreRef.current = false
    setLoading(true)
    setLoadingMore(false)
    setLoadError(null)
    const albumFilters = {
      ...nextFilters,
      excludeAlbumId: albumId,
      sharingGroupId: groupId,
    }
    setFilters(albumFilters)
    try {
      const page = await getPhotos(albumFilters)
      if (generation !== requestGenerationRef.current) return
      setPhotos(page.items)
      setNextCursor(page.next_cursor)
      setTotalCount(page.total_count)
    } catch (loadFailure) {
      if (generation !== requestGenerationRef.current) return
      if (isUnauthorizedError(loadFailure)) onUnauthorized()
      else setLoadError(t('photos.searchFailed'))
    } finally {
      if (generation === requestGenerationRef.current) setLoading(false)
    }
  }

  const loadMore = async () => {
    if (!nextCursor || loadingMoreRef.current) return
    const generation = requestGenerationRef.current
    loadingMoreRef.current = true
    setLoadingMore(true)
    setLoadError(null)
    try {
      const page = await getPhotos(filters, nextCursor)
      if (generation !== requestGenerationRef.current) return
      setPhotos((current) => [...current, ...page.items.filter((item) => !current.some(({ id }) => id === item.id))])
      setNextCursor(page.next_cursor)
      setTotalCount(page.total_count)
    } catch (loadFailure) {
      if (generation !== requestGenerationRef.current) return
      if (isUnauthorizedError(loadFailure)) onUnauthorized()
      else setLoadError(t('photos.moreFailed'))
    } finally {
      if (generation === requestGenerationRef.current) {
        loadingMoreRef.current = false
        setLoadingMore(false)
      }
    }
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
          <small>{t('albums.loadedCount', { total: totalCount, shown: photos.length })}</small>
        </div>
        <span>{t('albums.selectedCount', { count: selectedCount })}</span>
      </div>

      <PhotoSearchPanel filters={filters} timeline={null} disabled={loading} onSearch={(value) => void search(value)} />

      {loading ? (
        <div className="feature-loading" aria-label={t('photos.loadingList')}>
          <span className="spinner" />
        </div>
      ) : photos.length > 0 ? (
        <div className="photo-picker-grid">
          {photos.map((photo) => {
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
        hasMore={nextCursor !== null}
        loading={loadingMore}
        autoLoad={!loadError}
        onLoadMore={() => void loadMore()}
      />
      {(error || loadError) && (
        <p className="dialog-error" role="alert">
          {error || loadError}
        </p>
      )}
      <div className="dialog-actions">
        <button
          className="danger-button danger-button--filled icon-button"
          type="button"
          onClick={onClose}
          disabled={submitting}
        >
          <CancelIcon />
          {t('common.cancel')}
        </button>
        <button
          className="primary-button icon-button"
          type="button"
          disabled={submitting || selectedCount === 0}
          onClick={() => void onSubmit(selectedArray)}
        >
          <AddPhotoIcon />
          {submitting ? t('albums.adding') : t('albums.addSelected', { count: selectedCount })}
        </button>
      </div>
    </Dialog>
  )
}
