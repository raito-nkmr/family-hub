import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PhotoIcon } from '../../../shared/ui/icons'
import { getPhotoContentUrl, getPhotoThumbnailUrl } from '../api'
import { isVideoContentType } from '../contentType'
import { useCachedPhotoMediaUrl } from './usePhotoMediaCache'

interface PreviewPhoto {
  id: string
  original_filename: string
  content_type?: string
}

export function PhotoPreview({
  photo,
  className = '',
  source = 'thumbnail',
  onDisplayDimensions,
}: {
  photo: PreviewPhoto
  className?: string
  source?: 'thumbnail' | 'original'
  onDisplayDimensions?: (width: number, height: number) => void
}) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  const contentUrl = getPhotoContentUrl(photo.id)
  const isOriginalImage = source === 'original' && !isVideoContentType(photo.content_type)
  const cachedMedia = useCachedPhotoMediaUrl(contentUrl, isOriginalImage)

  if (failed || cachedMedia.failed) {
    return (
      <div className={`image-fallback ${className}`}>
        <PhotoIcon />
        <span>{t('photos.previewUnavailable')}</span>
      </div>
    )
  }

  if (source === 'original' && isVideoContentType(photo.content_type)) {
    return (
      <video
        className={className}
        controls
        playsInline
        preload="metadata"
        poster={getPhotoThumbnailUrl(photo.id)}
        aria-label={photo.original_filename}
        onLoadedMetadata={(event) => {
          const { videoWidth, videoHeight } = event.currentTarget
          if (videoWidth > 0 && videoHeight > 0) onDisplayDimensions?.(videoWidth, videoHeight)
        }}
        onError={() => setFailed(true)}
      >
        <source src={getPhotoContentUrl(photo.id)} type={photo.content_type} />
      </video>
    )
  }

  if (cachedMedia.loading) {
    return (
      <div className={`image-fallback ${className}`} aria-busy="true">
        <span className="spinner" />
      </div>
    )
  }

  return (
    <img
      className={className}
      src={source === 'thumbnail' ? getPhotoThumbnailUrl(photo.id) : (cachedMedia.url ?? contentUrl)}
      alt={photo.original_filename}
      loading={source === 'original' ? 'eager' : 'lazy'}
      onLoad={(event) => {
        const { naturalWidth, naturalHeight } = event.currentTarget
        if (naturalWidth > 0 && naturalHeight > 0) onDisplayDimensions?.(naturalWidth, naturalHeight)
      }}
      onError={() => setFailed(true)}
    />
  )
}
