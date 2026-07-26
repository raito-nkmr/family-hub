import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../shared/lib/format'
import { InfiniteScrollTrigger } from '../../shared/ui/InfiniteScrollTrigger'
import { PhotoActivityIcon, RefreshIcon } from '../../shared/ui/icons'
import type { PhotoActivityItem, PhotoListItem } from './api'
import { PhotoCard } from './components/PhotoCard'

interface PhotoActivityPageProps {
  items: PhotoActivityItem[]
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  error: string | null
  onRefresh: () => void
  onLoadMore: () => void
  onSelectPhoto: (photo: PhotoListItem) => void
}

interface ActivityGroup {
  key: string
  actorUsername: string
  eventType: PhotoActivityItem['event_type']
  occurredAt: string
  photos: PhotoListItem[]
}

function groupActivity(items: PhotoActivityItem[]): ActivityGroup[] {
  const groups = new Map<string, ActivityGroup>()
  for (const item of items) {
    const key = item.operation_id
    const current = groups.get(key)
    if (current) current.photos.push(item.photo)
    else {
      groups.set(key, {
        key,
        actorUsername: item.actor_username,
        eventType: item.event_type,
        occurredAt: item.occurred_at,
        photos: [item.photo],
      })
    }
  }
  return [...groups.values()]
}

export function PhotoActivityPage({
  items,
  loading,
  loadingMore,
  hasMore,
  error,
  onRefresh,
  onLoadMore,
  onSelectPhoto,
}: PhotoActivityPageProps) {
  const { t } = useTranslation()
  const groups = useMemo(() => groupActivity(items), [items])

  return (
    <main id="top" className="photo-activity-page">
      <header className="photo-activity-header">
        <div>
          <h1>{t('photoActivity.title')}</h1>
          <p>{t('photoActivity.description')}</p>
        </div>
        <button className="refresh-button" type="button" onClick={onRefresh} disabled={loading}>
          <RefreshIcon />
          <span>{t('common.refresh')}</span>
        </button>
      </header>

      {error && (
        <div className="page-message page-message--error" role="alert">
          {error}
        </div>
      )}
      {loading ? (
        <div className="photo-activity-loading" aria-label={t('photoActivity.loading')}>
          <span className="spinner" />
        </div>
      ) : groups.length === 0 ? (
        <div className="empty-state photo-activity-empty">
          <span>
            <PhotoActivityIcon />
          </span>
          <strong>{t('photoActivity.empty')}</strong>
          <p>{t('photoActivity.emptyHelp')}</p>
        </div>
      ) : (
        <div className="photo-activity-list">
          {groups.map((group) => (
            <article className="photo-activity-group" key={group.key}>
              <header>
                <div>
                  <strong>
                    {t(group.eventType === 'shared' ? 'photoActivity.shared' : 'photoActivity.uploaded', {
                      username: group.actorUsername,
                      count: group.photos.length,
                    })}
                  </strong>
                  <time dateTime={group.occurredAt}>{formatDateTime(group.occurredAt)}</time>
                </div>
              </header>
              <div className="photo-activity-grid">
                {group.photos.map((photo) => (
                  <PhotoCard key={photo.id} photo={photo} onSelect={onSelectPhoto} />
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
      <InfiniteScrollTrigger hasMore={hasMore} loading={loadingMore} autoLoad={!error} onLoadMore={onLoadMore} />
    </main>
  )
}
