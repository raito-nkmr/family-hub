import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PhotoIcon } from '../../../shared/ui/icons'
import { getPhotoContentUrl, getPhotoThumbnailUrl } from '../api'

interface PreviewPhoto {
  id: string
  original_filename: string
}

export function PhotoPreview({
  photo,
  className = '',
  source = 'thumbnail',
}: {
  photo: PreviewPhoto
  className?: string
  source?: 'thumbnail' | 'original'
}) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className={`image-fallback ${className}`}>
        <PhotoIcon />
        <span>{t('photos.previewUnavailable')}</span>
      </div>
    )
  }

  return (
    <img
      className={className}
      src={source === 'thumbnail' ? getPhotoThumbnailUrl(photo.id) : getPhotoContentUrl(photo.id)}
      alt={photo.original_filename}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}
