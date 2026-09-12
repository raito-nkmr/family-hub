import { useState, type CSSProperties, type PointerEventHandler } from 'react'
import { useTranslation } from 'react-i18next'
import { PhotoIcon } from '../../../shared/ui/icons'
import { getPhotoContentUrl, getPhotoPreviewUrl, getPhotoThumbnailUrl } from '../api'
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
  style,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
}: {
  photo: PreviewPhoto
  className?: string
  source?: 'thumbnail' | 'preview' | 'original'
  onDisplayDimensions?: (width: number, height: number) => void
  style?: CSSProperties
  onPointerDown?: PointerEventHandler<HTMLImageElement>
  onPointerMove?: PointerEventHandler<HTMLImageElement>
  onPointerUp?: PointerEventHandler<HTMLImageElement>
  onPointerCancel?: PointerEventHandler<HTMLImageElement>
}) {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  const contentUrl = getPhotoContentUrl(photo.id)
  const previewUrl = getPhotoPreviewUrl(photo.id)
  const isOriginalImage = source === 'original' && !isVideoContentType(photo.content_type)
  const isCachedImage = (source === 'preview' || isOriginalImage) && !isVideoContentType(photo.content_type)
  const mediaUrl = source === 'preview' ? previewUrl : contentUrl
  const cachedMedia = useCachedPhotoMediaUrl(mediaUrl, isCachedImage)

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
      src={source === 'thumbnail' ? getPhotoThumbnailUrl(photo.id) : (cachedMedia.url ?? mediaUrl)}
      alt={photo.original_filename}
      loading={source === 'thumbnail' ? 'lazy' : 'eager'}
      style={style}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
      onLoad={(event) => {
        const { naturalWidth, naturalHeight } = event.currentTarget
        if (naturalWidth > 0 && naturalHeight > 0) onDisplayDimensions?.(naturalWidth, naturalHeight)
      }}
      onError={() => setFailed(true)}
    />
  )
}
