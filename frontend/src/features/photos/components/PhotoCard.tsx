import { useTranslation } from 'react-i18next'
import { FavoriteIcon } from '../../../shared/ui/icons'
import type { PhotoListItem } from '../api'
import { isVideoContentType } from '../contentType'
import { PhotoPreview } from './PhotoPreview'

interface PhotoCardProps {
  photo: PhotoListItem
  selecting?: boolean
  selected?: boolean
  selectionDisabled?: boolean
  onSelect: (photo: PhotoListItem) => void
  onToggleSelection?: (photo: PhotoListItem) => void
}

export function PhotoCard({
  photo,
  selecting = false,
  selected = false,
  selectionDisabled = false,
  onSelect,
  onToggleSelection,
}: PhotoCardProps) {
  const { t } = useTranslation()
  return (
    <button
      className={`photo-card${selected ? ' photo-card--selected' : ''}${selectionDisabled ? ' photo-card--selection-disabled' : ''}`}
      type="button"
      aria-label={
        selecting
          ? t(selected ? 'bulkPhotoSharing.deselectPhoto' : 'bulkPhotoSharing.selectPhoto', {
              filename: photo.original_filename,
            })
          : t('photos.openPhoto', { filename: photo.original_filename })
      }
      aria-pressed={selecting ? selected : undefined}
      disabled={selectionDisabled}
      onClick={() => (selecting ? onToggleSelection?.(photo) : onSelect(photo))}
    >
      <div className="photo-card__image-wrap">
        <PhotoPreview photo={photo} className="photo-card__image" />
        {isVideoContentType(photo.content_type) && <span className="photo-card__media-type">{t('photos.video')}</span>}
        {selecting && (
          <span className="photo-card__selection-mark" aria-hidden="true">
            {selected ? '✓' : ''}
          </span>
        )}
        {photo.visibility === 'shared' && (
          <span className="photo-card__visibility photo-card__visibility--shared">{t('photos.family')}</span>
        )}
        {photo.is_favorite && (
          <span className="photo-card__favorite" aria-label={t('photoDetails.favorite')}>
            <FavoriteIcon />
          </span>
        )}
      </div>
    </button>
  )
}
