import type { usePhotoDashboard } from './usePhotoDashboard'
import type { usePhotoActivity } from './usePhotoActivity'
import { PhotoPage } from './PhotoPage'
import { PhotoActivityPage } from './PhotoActivityPage'

interface PhotoRouteProps {
  currentUserId: string
  dashboard: ReturnType<typeof usePhotoDashboard>
}

export function PhotoRoute({ currentUserId, dashboard }: PhotoRouteProps) {
  return (
    <PhotoPage
      currentUserId={currentUserId}
      storage={dashboard.storage}
      photos={dashboard.photos}
      filters={dashboard.photoFilters}
      timeline={dashboard.timeline}
      totalCount={dashboard.totalCount}
      hasMore={dashboard.hasMore}
      uploadQueue={dashboard.uploadQueue}
      uploading={dashboard.uploading}
      groups={dashboard.groups}
      uploadGroupIds={dashboard.uploadGroupIds}
      uploadVisibilityLocked={dashboard.uploadVisibilityLocked}
      uploadMessage={dashboard.uploadMessage}
      loading={dashboard.loading}
      loadingMore={dashboard.loadingMore}
      pageError={dashboard.pageError}
      fileInputRef={dashboard.fileInputRef}
      onFileChange={dashboard.selectFiles}
      onUploadGroupSelectionChange={dashboard.changeUploadGroups}
      onUpload={() => void dashboard.upload()}
      onCancelUpload={() => void dashboard.cancelUpload()}
      onRefresh={() => void dashboard.refresh()}
      onSearch={(filters) => void dashboard.search(filters)}
      onTimelineYearChange={(year) => void dashboard.changeTimelineYear(year)}
      onLoadMore={() => void dashboard.loadMore()}
      onSelectPhoto={dashboard.selectPhoto}
      onBulkAddSharing={dashboard.bulkAddSharing}
    />
  )
}

interface PhotoActivityRouteProps {
  activity: ReturnType<typeof usePhotoActivity>
  onSelectPhoto: ReturnType<typeof usePhotoDashboard>['selectPhoto']
}

export function PhotoActivityRoute({ activity, onSelectPhoto }: PhotoActivityRouteProps) {
  return (
    <PhotoActivityPage
      items={activity.items}
      loading={activity.loading}
      loadingMore={activity.loadingMore}
      hasMore={activity.hasMore}
      error={activity.error}
      onRefresh={() => void activity.refresh()}
      onLoadMore={() => void activity.loadMore()}
      onSelectPhoto={onSelectPhoto}
    />
  )
}
