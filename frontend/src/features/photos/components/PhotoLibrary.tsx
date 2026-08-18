import type { TFunction } from 'i18next'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CancelIcon, ExportIcon, PhotoIcon, RefreshIcon, SelectIcon, ShareIcon } from '../../../shared/ui/icons'
import { InfiniteScrollTrigger } from '../../../shared/ui/InfiniteScrollTrigger'
import type { PhotoFilters, PhotoListItem, PhotoSearchOptions, PhotoTimeline } from '../api'
import { PhotoCard } from './PhotoCard'
import { PhotoGridDensity } from './PhotoGridDensity'
import { PhotoSearchPanel } from './PhotoSearchPanel'
import { usePhotoGridColumns } from './usePhotoGridColumns'

interface PhotoLibraryProps {
  currentUserId: string
  photos: PhotoListItem[]
  filters: PhotoFilters
  searchOptions?: PhotoSearchOptions | null
  searchOptionsLoading?: boolean
  timeline: PhotoTimeline | null
  totalCount: number
  loading: boolean
  loadingMore: boolean
  hasMore: boolean
  pageError: string | null
  onRefresh: () => void
  onSearch: (filters: PhotoFilters) => void
  onTimelineYearChange: (year: number) => void
  onLoadMore: () => void
  onSelectPhoto: (photo: PhotoListItem) => void
  onRequestBulkSharing: (photoIds: string[]) => void
  onRequestExport: (photoIds: string[]) => void
}

interface PhotoGroup {
  key: string
  title: string
  items: PhotoListItem[]
}

function groupTitle(photo: PhotoListItem, language: string, t: TFunction): { key: string; title: string } {
  const source = photo.captured_at ?? photo.uploaded_at
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    timeZone: 'Asia/Tokyo',
  }).formatToParts(new Date(source))
  const year = parts.find(({ type }) => type === 'year')?.value
  const month = parts.find(({ type }) => type === 'month')?.value
  const key = `${year}-${month}`
  const formatted = new Intl.DateTimeFormat(language === 'ja' ? 'ja-JP' : 'en-US', {
    year: 'numeric',
    month: 'long',
    timeZone: 'Asia/Tokyo',
  }).format(new Date(source))
  return photo.captured_at
    ? { key: `captured-${key}`, title: formatted }
    : { key: `unknown-${key}`, title: `${t('photos.capturedUnknown')} · ${t('photos.addedOn', { date: formatted })}` }
}

function groupPhotos(photos: PhotoListItem[], language: string, t: TFunction): PhotoGroup[] {
  return photos.reduce<PhotoGroup[]>((groups, photo) => {
    const group = groupTitle(photo, language, t)
    const previous = groups.at(-1)
    if (previous?.key === group.key) previous.items.push(photo)
    else groups.push({ ...group, items: [photo] })
    return groups
  }, [])
}

export function PhotoLibrary({
  currentUserId,
  photos,
  filters,
  searchOptions = null,
  searchOptionsLoading = false,
  timeline,
  totalCount,
  loading,
  loadingMore,
  hasMore,
  pageError,
  onRefresh,
  onSearch,
  onTimelineYearChange,
  onLoadMore,
  onSelectPhoto,
  onRequestBulkSharing,
  onRequestExport,
}: PhotoLibraryProps) {
  const { t, i18n } = useTranslation()
  const { gridColumns, changeGridColumns } = usePhotoGridColumns()
  const [selecting, setSelecting] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const groups = groupPhotos(photos, i18n.resolvedLanguage ?? 'en', t)
  const initialLoading = loading && timeline === null

  const stopSelecting = () => {
    setSelecting(false)
    setSelectedIds(new Set())
  }

  const toggleSelection = (photo: PhotoListItem) => {
    if (photo.uploaded_by_user_id !== currentUserId) return
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(photo.id)) next.delete(photo.id)
      else if (next.size < 100) next.add(photo.id)
      return next
    })
  }

  return (
    <section className="library" aria-labelledby="library-heading" aria-busy={loading}>
      <div className="section-heading">
        <div>
          <h2 id="library-heading">{t('photos.listTitle')}</h2>
          <p>
            {totalCount > 0 ? t('photos.count', { total: totalCount, shown: photos.length }) : t('photos.emptyList')}
          </p>
        </div>
        <div className="section-heading__actions">
          <button
            className={
              selecting
                ? 'photo-selection-toggle danger-button danger-button--filled'
                : 'photo-selection-toggle secondary-button'
            }
            type="button"
            onClick={() => (selecting ? stopSelecting() : setSelecting(true))}
            disabled={loading || photos.every((photo) => photo.uploaded_by_user_id !== currentUserId)}
          >
            <span
              className={
                selecting
                  ? 'photo-selection-toggle__content photo-selection-toggle__content--hidden'
                  : 'photo-selection-toggle__content'
              }
              aria-hidden={selecting}
            >
              <SelectIcon />
              {t('bulkPhotoSharing.select')}
            </span>
            <span
              className={
                selecting
                  ? 'photo-selection-toggle__content'
                  : 'photo-selection-toggle__content photo-selection-toggle__content--hidden'
              }
              aria-hidden={!selecting}
            >
              <CancelIcon />
              {t('common.cancel')}
            </span>
          </button>
          <button className="refresh-button" type="button" onClick={onRefresh} disabled={loading || selecting}>
            <RefreshIcon />
            <span>{t('common.refresh')}</span>
          </button>
        </div>
      </div>

      {selecting ? (
        <div className="bulk-selection-bar" role="status">
          <span>{t('bulkPhotoSharing.selectedCount', { count: selectedIds.size, max: 100 })}</span>
          <div className="bulk-selection-bar__actions">
            <button
              type="button"
              className="secondary-button icon-button"
              disabled={selectedIds.size === 0}
              onClick={() => {
                onRequestExport([...selectedIds])
                stopSelecting()
              }}
            >
              <ExportIcon />
              {t('photoExport.exportSelected')}
            </button>
            <button
              type="button"
              className="primary-button icon-button"
              disabled={selectedIds.size === 0}
              onClick={() => {
                onRequestBulkSharing([...selectedIds])
                stopSelecting()
              }}
            >
              <ShareIcon />
              {t('bulkPhotoSharing.openDialog')}
            </button>
          </div>
        </div>
      ) : (
        <PhotoSearchPanel
          filters={filters}
          searchOptions={searchOptions}
          searchOptionsLoading={searchOptionsLoading}
          timeline={timeline}
          disabled={loading}
          onSearch={onSearch}
          onTimelineYearChange={onTimelineYearChange}
        />
      )}

      {pageError && (
        <div className="page-message page-message--error" role="alert">
          {pageError}
        </div>
      )}

      {photos.length > 0 && <PhotoGridDensity columns={gridColumns} onChange={changeGridColumns} />}

      {initialLoading ? (
        <div className="loading-grid" aria-label={t('photos.loadingList')}>
          {Array.from({ length: 4 }, (_, index) => (
            <div className="photo-skeleton" key={index} />
          ))}
        </div>
      ) : photos.length > 0 ? (
        <>
          <div className="photo-timeline">
            {groups.map((group, index) => (
              <section className="photo-month" key={`${group.key}-${index}`} aria-labelledby={`photo-month-${index}`}>
                <div className="photo-month__heading">
                  <h3 id={`photo-month-${index}`}>{group.title}</h3>
                  <span>{t('photos.monthCount', { count: group.items.length })}</span>
                </div>
                <div className={`photo-grid photo-grid--columns-${gridColumns}`}>
                  {group.items.map((photo) => (
                    <PhotoCard
                      key={photo.id}
                      photo={photo}
                      selecting={selecting}
                      selected={selectedIds.has(photo.id)}
                      selectionDisabled={
                        selecting &&
                        (photo.uploaded_by_user_id !== currentUserId ||
                          (selectedIds.size >= 100 && !selectedIds.has(photo.id)))
                      }
                      onSelect={onSelectPhoto}
                      onToggleSelection={toggleSelection}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
          <InfiniteScrollTrigger
            hasMore={hasMore}
            loading={loading || loadingMore}
            autoLoad={!loading && !pageError}
            onLoadMore={onLoadMore}
          />
        </>
      ) : (
        <div className="empty-state">
          <span>
            <PhotoIcon />
          </span>
          <h3>{t('photos.noResults')}</h3>
          <p>{t('photos.noResultsHelp')}</p>
        </div>
      )}
    </section>
  )
}
