import type { ReactNode } from 'react'
import { PhotoPreview, type Photo } from '../../photos/public'

interface AlbumPhotoThumbnailProps {
  photo: Pick<Photo, 'id' | 'original_filename'>
  className: string
  children?: ReactNode
}

export function AlbumPhotoThumbnail({ photo, className, children }: AlbumPhotoThumbnailProps) {
  return (
    <span className={`album-photo-thumbnail ${className}`} data-photo-id={photo.id}>
      <PhotoPreview photo={photo} className="album-photo-thumbnail__image" />
      {children}
    </span>
  )
}
