import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../../shared/lib/format'
import type { Photo } from '../../photos/public'
import { PhotoPreview } from '../../photos/public'

interface AlbumPhotoGridProps {
  photos: Photo[]
  coverPhotoId: string | null
  organizing: boolean
  selectedIds: ReadonlySet<string>
  removingPhotoIds: ReadonlySet<string>
  onSelect: (photo: Photo) => void
  onToggle: (photoId: string) => void
}

export function AlbumPhotoGrid({
  photos,
  coverPhotoId,
  organizing,
  selectedIds,
  removingPhotoIds,
  onSelect,
  onToggle,
}: AlbumPhotoGridProps) {
  const { t } = useTranslation()
  return (
    <div className="album-photo-grid">
      {photos.map((photo) => {
        const selected = selectedIds.has(photo.id)
        const removing = removingPhotoIds.has(photo.id)
        const isCover = coverPhotoId === photo.id
        return (
          <article
            className={`album-photo-card${selected ? ' album-photo-card--selected' : ''}${removing ? ' album-photo-card--busy' : ''}`}
            key={photo.id}
          >
            <button
              className="album-photo-card__preview"
              type="button"
              aria-pressed={organizing ? selected : undefined}
              disabled={removing}
              onClick={() => (organizing ? onToggle(photo.id) : onSelect(photo))}
            >
              <div className="album-photo-card__image-wrap">
                <PhotoPreview photo={photo} className="album-photo-card__image" />
                {isCover && <span className="album-photo-card__cover-badge">{t('albums.coverBadge')}</span>}
                {organizing && (
                  <span className="album-photo-card__selection" aria-hidden="true">
                    {selected ? '✓' : ''}
                  </span>
                )}
              </div>
              <span className="album-photo-card__body">
                <strong>{photo.original_filename}</strong>
                <span>{photo.captured_at ? formatDateTime(photo.captured_at) : t('photos.capturedUnknown')}</span>
              </span>
            </button>
          </article>
        )
      })}
    </div>
  )
}
