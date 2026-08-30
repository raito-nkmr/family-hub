import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../../shared/lib/format'
import { EmptyState } from '../../../shared/ui/EmptyState'
import { InfiniteScrollTrigger } from '../../../shared/ui/InfiniteScrollTrigger'
import { PageMessage } from '../../../shared/ui/PageMessage'
import { AlbumIcon, BackIcon, CheckIcon, DeleteIcon, EditIcon, PhotoIcon, PlusIcon } from '../../../shared/ui/icons'
import type { Photo } from '../../photos/public'
import type { AlbumDetail } from '../api'
import { AlbumPhotoThumbnail } from './AlbumPhotoThumbnail'
import { AlbumPhotoGrid } from './AlbumPhotoGrid'

interface AlbumDetailViewProps {
  album: AlbumDetail
  error: string | null
  removingPhotoIds: ReadonlySet<string>
  hasMore: boolean
  loadingMore: boolean
  loadMoreFailed: boolean
  onBack: () => void
  onEdit: () => void
  onDelete: () => void
  onAddPhotos: () => void
  onSelectPhoto: (photo: Photo) => void
  onRemovePhotos: (photoIds: string[]) => Promise<boolean>
  onSetCover: (photo: Photo) => Promise<boolean>
  onLoadMore: () => void
}

export function AlbumDetailView({
  album,
  error,
  removingPhotoIds,
  hasMore,
  loadingMore,
  loadMoreFailed,
  onBack,
  onEdit,
  onDelete,
  onAddPhotos,
  onSelectPhoto,
  onRemovePhotos,
  onSetCover,
  onLoadMore,
}: AlbumDetailViewProps) {
  const { t } = useTranslation()
  const coverPhoto = album.cover_photo_id
    ? (album.photos.find((photo) => photo.id === album.cover_photo_id) ?? {
        id: album.cover_photo_id,
        original_filename: '',
      })
    : null
  const [organizing, setOrganizing] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const selectedPhotos = useMemo(
    () => album.photos.filter((photo) => selectedIds.has(photo.id)),
    [album.photos, selectedIds],
  )
  const busy = removingPhotoIds.size > 0

  const toggleOrganizing = () => {
    setOrganizing((current) => !current)
    setSelectedIds(new Set())
  }

  const togglePhoto = (photoId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(photoId)) next.delete(photoId)
      else next.add(photoId)
      return next
    })
  }

  const setSelectedCover = async () => {
    const photo = selectedPhotos[0]
    if (photo && (await onSetCover(photo))) setSelectedIds(new Set())
  }

  const removeSelectedPhotos = async () => {
    if (await onRemovePhotos(selectedPhotos.map((photo) => photo.id))) setSelectedIds(new Set())
  }

  return (
    <main id="top" className="album-detail-page">
      <button className="back-button" type="button" onClick={onBack}>
        <BackIcon />
        {t('albums.back')}
      </button>

      <header className="album-detail-header">
        {coverPhoto ? (
          <AlbumPhotoThumbnail photo={coverPhoto} className="album-detail-header__cover" />
        ) : (
          <div className="album-detail-header__cover">
            <AlbumIcon />
          </div>
        )}
        <div className="album-detail-header__copy">
          <p className="eyebrow">{t('albums.detailEyebrow')}</p>
          <h1>{album.title}</h1>
          <p>{album.description ?? t('albums.noDescription')}</p>
          {album.group_names.length > 0 && <span>{album.group_names.join(', ')}</span>}
          <span>
            {t('albums.photosCount', { count: album.photo_count })} ·{' '}
            {t('albums.updated', { date: formatDateTime(album.updated_at) })}
          </span>
        </div>
        <div className="album-detail-header__actions">
          <button className="secondary-button icon-button album-detail-header__edit" type="button" onClick={onEdit}>
            <EditIcon />
            {t('albums.editAction')}
          </button>
          <button className="danger-button icon-button" type="button" onClick={onDelete}>
            <DeleteIcon />
            {t('albums.delete')}
          </button>
        </div>
      </header>

      <section className="album-photos" aria-labelledby="album-photos-heading">
        <div className="section-heading album-photos__heading">
          <div>
            <h2 id="album-photos-heading">{t('albums.photos')}</h2>
            <p>{organizing ? t('albums.organizeHelp') : t('albums.browseHelp')}</p>
          </div>
          <div className="album-photos__heading-actions">
            <button className="primary-button icon-button" type="button" onClick={onAddPhotos} disabled={busy}>
              <PlusIcon />
              {t('albums.addPhotos')}
            </button>
            {album.photos.length > 0 && (
              <button
                className={
                  organizing ? 'album-organize-toggle success-button' : 'album-organize-toggle secondary-button'
                }
                type="button"
                aria-pressed={organizing}
                onClick={toggleOrganizing}
                disabled={busy}
              >
                <span
                  className={
                    organizing
                      ? 'album-organize-toggle__content album-organize-toggle__content--hidden'
                      : 'album-organize-toggle__content'
                  }
                  aria-hidden={organizing}
                >
                  <EditIcon />
                  {t('albums.organizePhotos')}
                </span>
                <span
                  className={
                    organizing
                      ? 'album-organize-toggle__content'
                      : 'album-organize-toggle__content album-organize-toggle__content--hidden'
                  }
                  aria-hidden={!organizing}
                >
                  <CheckIcon />
                  {t('common.done')}
                </span>
              </button>
            )}
          </div>
        </div>

        {error && <PageMessage>{error}</PageMessage>}

        {album.photos.length > 0 ? (
          <AlbumPhotoGrid
            photos={album.photos}
            coverPhotoId={album.cover_photo_id}
            organizing={organizing}
            selectedIds={selectedIds}
            removingPhotoIds={removingPhotoIds}
            onSelect={onSelectPhoto}
            onToggle={togglePhoto}
          />
        ) : (
          <EmptyState
            className="album-empty-state"
            icon={<AlbumIcon />}
            title={t('albums.emptyPhotos')}
            description={t('albums.emptyPhotosHelp')}
          />
        )}

        <InfiniteScrollTrigger
          hasMore={hasMore}
          loading={loadingMore}
          autoLoad={!loadMoreFailed}
          onLoadMore={onLoadMore}
        />

        {organizing && album.photos.length > 0 && (
          <div className="album-organize-bar" aria-label={t('albums.organizeActions')}>
            <span className="album-organize-bar__count" aria-live="polite">
              {t('albums.selectedCount', { count: selectedPhotos.length })}
            </span>
            <div className="album-organize-bar__actions">
              <button
                className="secondary-button icon-button"
                type="button"
                disabled={busy || selectedPhotos.length !== 1 || selectedPhotos[0]?.id === album.cover_photo_id}
                onClick={() => void setSelectedCover()}
              >
                <PhotoIcon />
                {selectedPhotos[0]?.id === album.cover_photo_id ? t('albums.currentCover') : t('albums.setCover')}
              </button>
              <button
                className="danger-button icon-button"
                type="button"
                disabled={busy || selectedPhotos.length === 0}
                onClick={() => void removeSelectedPhotos()}
              >
                <DeleteIcon />
                {busy ? t('albums.removing') : t('albums.removeSelected')}
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
