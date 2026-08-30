import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../../shared/lib/format'
import { AlbumIcon } from '../../../shared/ui/icons'
import { getPhotoThumbnailUrl } from '../../photos/api'
import type { Album } from '../api'

export function AlbumCard({ album, onSelect }: { album: Album; onSelect: (album: Album) => void }) {
  const { t } = useTranslation()
  return (
    <button className="album-card" type="button" onClick={() => onSelect(album)}>
      <span className="album-card__icon">
        {album.cover_photo_id ? <img src={getPhotoThumbnailUrl(album.cover_photo_id)} alt="" /> : <AlbumIcon />}
      </span>
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
