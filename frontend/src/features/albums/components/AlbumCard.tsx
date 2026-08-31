import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../../shared/lib/format'
import { AlbumIcon } from '../../../shared/ui/icons'
import type { Album } from '../api'
import { AlbumPhotoThumbnail } from './AlbumPhotoThumbnail'

export function AlbumCard({ album, onSelect }: { album: Album; onSelect: (album: Album) => void }) {
  const { t } = useTranslation()
  return (
    <button className="album-card" type="button" onClick={() => onSelect(album)}>
      {album.cover_photo_id ? (
        <AlbumPhotoThumbnail photo={{ id: album.cover_photo_id, original_filename: '' }} className="album-card__icon" />
      ) : (
        <span className="album-card__icon">
          <AlbumIcon />
        </span>
      )}
      <span className="album-card__body">
        <strong>{album.title}</strong>
        <span>{album.description ?? t('albums.noDescription')}</span>
        {album.group_names.length > 0 && <span>{album.group_names.join(', ')}</span>}
      </span>
      <span className="album-card__meta">
        <span>{t('albums.photosCount', { count: album.photo_count })}</span>
        <time dateTime={album.updated_at}>{t('albums.updated', { date: formatDateTime(album.updated_at) })}</time>
      </span>
    </button>
  )
}
