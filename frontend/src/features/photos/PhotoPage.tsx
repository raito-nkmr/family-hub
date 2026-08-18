import { useState, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import type { FamilyGroup } from '../groups/api'
import {
  getPhotoExportUrl,
  type BulkSharingResult,
  type PhotoFilters,
  type PhotoListItem,
  type PhotoSearchOptions,
  type PhotoTimeline,
  type StorageStatus,
} from './api'
import { BulkPhotoSharingDialog } from './components/BulkPhotoSharingDialog'
import { PhotoLibrary } from './components/PhotoLibrary'
import { PhotoUploadCard, type UploadMessage } from './components/PhotoUploadCard'
import type { QueuedUpload } from './uploadTypes'

interface PhotoPageProps {
  currentUserId: string
  storage: StorageStatus | null
  photos: PhotoListItem[]
  filters: PhotoFilters
  timeline: PhotoTimeline | null
  totalCount: number
  hasMore: boolean
  uploadQueue: QueuedUpload[]
  uploading: boolean
  groups: FamilyGroup[]
  searchOptions: PhotoSearchOptions | null
  searchOptionsLoading: boolean
  uploadGroupIds: string[]
  uploadVisibilityLocked: boolean
  uploadMessage: UploadMessage | null
  loading: boolean
  loadingMore: boolean
  pageError: string | null
  fileInputRef: RefObject<HTMLInputElement | null>
  onFileChange: (files: File[]) => void
  onUploadGroupSelectionChange: (groupIds: string[]) => void
  onUpload: () => void
  onCancelUpload: () => void
  onRefresh: () => void
  onSearch: (filters: PhotoFilters) => void
  onTimelineYearChange: (year: number) => void
  onLoadMore: () => void
  onSelectPhoto: (photo: PhotoListItem) => void
  onBulkAddSharing: (photoIds: string[], groupIds: string[]) => Promise<BulkSharingResult>
}

export function PhotoPage({
  currentUserId,
  storage,
  photos,
  filters,
  timeline,
  totalCount,
  hasMore,
  uploadQueue,
  uploading,
  groups,
  searchOptions,
  searchOptionsLoading,
  uploadGroupIds,
  uploadVisibilityLocked,
  uploadMessage,
  loading,
  loadingMore,
  pageError,
  fileInputRef,
  onFileChange,
  onUploadGroupSelectionChange,
  onUpload,
  onCancelUpload,
  onRefresh,
  onSearch,
  onTimelineYearChange,
  onLoadMore,
  onSelectPhoto,
  onBulkAddSharing,
}: PhotoPageProps) {
  const { t } = useTranslation()
  const [bulkPhotoIds, setBulkPhotoIds] = useState<string[] | null>(null)
  const [bulkSharingBusy, setBulkSharingBusy] = useState(false)
  const [bulkSharingError, setBulkSharingError] = useState<string | null>(null)
  const [bulkSharingMessage, setBulkSharingMessage] = useState<string | null>(null)
  const [exportMessage, setExportMessage] = useState<string | null>(null)

  const openBulkSharing = (photoIds: string[]) => {
    setBulkSharingError(null)
    setBulkPhotoIds(photoIds)
  }

  const submitBulkSharing = async (groupIds: string[]) => {
    if (!bulkPhotoIds) return
    setBulkSharingBusy(true)
    setBulkSharingError(null)
    try {
      const result = await onBulkAddSharing(bulkPhotoIds, groupIds)
      setBulkSharingMessage(
        t('bulkPhotoSharing.result', { updated: result.updated_count, unchanged: result.unchanged_count }),
      )
      setBulkPhotoIds(null)
    } catch {
      setBulkSharingError(t('bulkPhotoSharing.failed'))
    } finally {
      setBulkSharingBusy(false)
    }
  }

  const exportSelected = (photoIds: string[]) => {
    const link = document.createElement('a')
    link.href = getPhotoExportUrl(photoIds)
    link.download = 'family-hub-photos.zip'
    link.hidden = true
    document.body.append(link)
    link.click()
    link.remove()
    setExportMessage(t('photoExport.started', { count: photoIds.length }))
  }

  return (
    <main id="top">
      <section className="hero">
        <div className="hero__copy">
          <h1>{t('photos.title')}</h1>
          <p className="hero__description">{t('photos.description')}</p>
        </div>

        <PhotoUploadCard
          storage={storage}
          uploadQueue={uploadQueue}
          uploading={uploading}
          groups={groups}
          selectedGroupIds={uploadGroupIds}
          visibilityLocked={uploadVisibilityLocked}
          uploadMessage={uploadMessage}
          fileInputRef={fileInputRef}
          onFileChange={onFileChange}
          onGroupSelectionChange={onUploadGroupSelectionChange}
          onUpload={onUpload}
          onCancel={onCancelUpload}
          onShareSavedPhotos={openBulkSharing}
        />
      </section>

      {bulkSharingMessage && (
        <p className="page-message page-message--success" role="status">
          {bulkSharingMessage}
        </p>
      )}
      {exportMessage && (
        <p className="page-message page-message--success" role="status">
          {exportMessage}
        </p>
      )}
      <PhotoLibrary
        currentUserId={currentUserId}
        photos={photos}
        filters={filters}
        searchOptions={searchOptions}
        searchOptionsLoading={searchOptionsLoading}
        timeline={timeline}
        totalCount={totalCount}
        hasMore={hasMore}
        loading={loading}
        loadingMore={loadingMore}
        pageError={pageError}
        onRefresh={onRefresh}
        onSearch={onSearch}
        onTimelineYearChange={onTimelineYearChange}
        onLoadMore={onLoadMore}
        onSelectPhoto={onSelectPhoto}
        onRequestBulkSharing={openBulkSharing}
        onRequestExport={exportSelected}
      />
      {bulkPhotoIds && (
        <BulkPhotoSharingDialog
          photoCount={bulkPhotoIds.length}
          groups={groups}
          busy={bulkSharingBusy}
          error={bulkSharingError}
          onSubmit={(groupIds) => void submitBulkSharing(groupIds)}
          onClose={() => setBulkPhotoIds(null)}
        />
      )}
    </main>
  )
}
