import { useTranslation } from 'react-i18next'
import { CheckIcon, FavoriteIcon, ShareIcon, VideoLibraryIcon } from '../../../shared/ui/icons'
import type { PhotoListItem } from '../api'
import { isVideoContentType } from '../contentType'
import { PhotoBadge } from './PhotoBadge'
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
        {isVideoContentType(photo.content_type) && (
          <PhotoBadge variant="video" position="top-right" label={t('photos.video')} icon={<VideoLibraryIcon />}>
            {t('photos.video')}
          </PhotoBadge>
        )}
        {selecting && (
          <PhotoBadge
            variant="selection"
            position="bottom-left"
            label={t(selected ? 'bulkPhotoSharing.deselectPhoto' : 'bulkPhotoSharing.selectPhoto', {
              filename: photo.original_filename,
            })}
            active={selected}
            icon={selected ? <CheckIcon /> : undefined}
          />
        )}
        {photo.visibility === 'shared' && (
          <PhotoBadge variant="shared" position="bottom-right" label={t('photos.family')} icon={<ShareIcon />}>
            {t('photos.family')}
          </PhotoBadge>
        )}
        {photo.is_favorite && (
          <PhotoBadge
            variant="favorite"
            position="top-left"
            label={t('photoDetails.favorite')}
            icon={<FavoriteIcon />}
          />
        )}
      </div>
    </button>
  )
}
