import type {
  BulkPhotoSharingAdd,
  BulkPhotoSharingResponse,
  PhotoActivityItemResponse,
  PhotoActivityResponse,
  PhotoActivitySeenUpdate,
  PhotoListItemResponse,
  PhotoListResponse,
  PhotoResponse,
  PhotoSearchOptionsResponse,
  PhotoTimelineResponse,
  PhotoUpdate,
  PhotoVisibility as ApiPhotoVisibility,
  StorageStatusCode as ApiStorageStatusCode,
  StorageStatusResponse,
  TrashedPhotoListResponse,
} from '../../shared/api/generated'
import {
  addPhotoFavoriteApiV1PhotosPhotoIdFavoritePut,
  bulkAddPhotoSharingApiV1PhotosBulkSharingPost,
  getPhotoApiV1PhotosPhotoIdGet,
  getPhotoSearchOptionsApiV1PhotosSearchOptionsGet,
  getPhotoTimelineApiV1PhotosTimelineGet,
  getStorageStatusApiV1PhotosStorageStatusGet,
  listPhotoActivityApiV1PhotosActivityGet,
  listPhotosApiV1PhotosGet,
  listTrashedPhotosApiV1PhotosTrashGet,
  markPhotoActivitySeenApiV1PhotosActivitySeenPost,
  permanentlyDeletePhotoApiV1PhotosPhotoIdPermanentDelete,
  removePhotoFavoriteApiV1PhotosPhotoIdFavoriteDelete,
  removePhotoGroupShareAsAdminApiV1PhotosPhotoIdGroupsGroupIdDelete,
  restorePhotoApiV1PhotosPhotoIdRestorePost,
  trashPhotoApiV1PhotosPhotoIdDelete,
  updatePhotoMetadataApiV1PhotosPhotoIdPatch,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type StorageStatusCode = ApiStorageStatusCode
export type StorageStatus = StorageStatusResponse
export type Photo = PhotoResponse
export type PhotoSearchOptions = PhotoSearchOptionsResponse
export type PhotoListItem = PhotoListItemResponse
export type PhotoPage = PhotoListResponse
export type PhotoActivity = PhotoActivityResponse
export type PhotoActivityItem = PhotoActivityItemResponse
export type BulkSharingResult = BulkPhotoSharingResponse
export type PhotoTimeline = PhotoTimelineResponse
export type PhotoVisibility = ApiPhotoVisibility
export type TrashedPhotoList = TrashedPhotoListResponse

export interface PhotoCaptureTimes {
  captured_at_original: string | null
  captured_at_override: string | null
}

export function getPhotoCaptureTime(photo: PhotoCaptureTimes): string | null {
  return photo.captured_at_override ?? photo.captured_at_original
}

export function getStorageStatus(signal?: AbortSignal): Promise<StorageStatus> {
  return sdkData(getStorageStatusApiV1PhotosStorageStatusGet({ signal }))
}

export interface PhotoFilters {
  q?: string
  dateFrom?: string
  dateTo?: string
  uploaderId?: string
  mineOnly?: boolean
  visibility?: PhotoVisibility
  capturedAtKnown?: boolean
  albumId?: string
  excludeAlbumId?: string
  sharingGroupId?: string
  favorite?: boolean
}

export async function getPhotos(
  filters: PhotoFilters = {},
  cursor?: string,
  signal?: AbortSignal,
  limit = 50,
): Promise<PhotoPage> {
  return sdkData(
    listPhotosApiV1PhotosGet({
      query: {
        limit,
        cursor,
        q: filters.q?.trim() || undefined,
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
        uploader_id: filters.uploaderId,
        mine_only: filters.mineOnly,
        visibility: filters.visibility,
        captured_at_known: filters.capturedAtKnown,
        album_id: filters.albumId,
        exclude_album_id: filters.excludeAlbumId,
        sharing_group_id: filters.sharingGroupId,
        favorite: filters.favorite,
      },
      signal,
    }),
  )
}

export function getPhotoSearchOptions(signal?: AbortSignal): Promise<PhotoSearchOptions> {
  return sdkData(getPhotoSearchOptionsApiV1PhotosSearchOptionsGet({ signal }))
}

export function getPhoto(photoId: string, signal?: AbortSignal): Promise<Photo> {
  return sdkData(getPhotoApiV1PhotosPhotoIdGet({ path: { photo_id: photoId }, signal }))
}

export function getTrashedPhotos(signal?: AbortSignal, cursor?: string): Promise<TrashedPhotoList> {
  return sdkData(listTrashedPhotosApiV1PhotosTrashGet({ query: { limit: 50, cursor }, signal }))
}

export function trashPhoto(photoId: string): Promise<Photo> {
  return sdkData(trashPhotoApiV1PhotosPhotoIdDelete({ path: { photo_id: photoId } }))
}

export function restorePhoto(photoId: string): Promise<Photo> {
  return sdkData(restorePhotoApiV1PhotosPhotoIdRestorePost({ path: { photo_id: photoId } }))
}

export function permanentlyDeletePhoto(photoId: string): Promise<void> {
  return sdkData(permanentlyDeletePhotoApiV1PhotosPhotoIdPermanentDelete({ path: { photo_id: photoId } }))
}

export function getTrashedPhotoThumbnailUrl(photoId: string): string {
  return `/api/v1/photos/trash/${encodeURIComponent(photoId)}/thumbnail`
}

export function getPhotoTimeline(year: number, signal?: AbortSignal): Promise<PhotoTimeline> {
  return sdkData(getPhotoTimelineApiV1PhotosTimelineGet({ query: { year }, signal }))
}

export function getPhotoActivity(cursor?: string, signal?: AbortSignal): Promise<PhotoActivity> {
  return sdkData(listPhotoActivityApiV1PhotosActivityGet({ query: { limit: 30, cursor }, signal }))
}

export function markPhotoActivitySeen(eventId: string): Promise<void> {
  const body: PhotoActivitySeenUpdate = { event_id: eventId }
  return sdkData(markPhotoActivitySeenApiV1PhotosActivitySeenPost({ body }))
}

export function removePhotoGroupShareAsAdmin(
  photoId: string,
  groupId: string,
  currentPassword: string,
): Promise<Photo> {
  return sdkData(
    removePhotoGroupShareAsAdminApiV1PhotosPhotoIdGroupsGroupIdDelete({
      path: { photo_id: photoId, group_id: groupId },
      body: { current_password: currentPassword },
    }),
  )
}

export function addBulkPhotoSharing(photoIds: string[], groupIds: string[]): Promise<BulkSharingResult> {
  const body: BulkPhotoSharingAdd = { photo_ids: photoIds, group_ids_to_add: groupIds }
  return sdkData(bulkAddPhotoSharingApiV1PhotosBulkSharingPost({ body }))
}

export function getPhotoExportUrl(photoIds: string[]): string {
  const params = new URLSearchParams()
  photoIds.forEach((photoId) => params.append('photo_ids', photoId))
  return `/api/v1/photos/export?${params}`
}

export function updatePhoto(photoId: string, changes: PhotoUpdate): Promise<Photo> {
  return sdkData(updatePhotoMetadataApiV1PhotosPhotoIdPatch({ path: { photo_id: photoId }, body: changes }))
}

export function setPhotoFavorite(photoId: string, favorite: boolean): Promise<Photo> {
  const options = { path: { photo_id: photoId } }
  return sdkData(
    favorite
      ? addPhotoFavoriteApiV1PhotosPhotoIdFavoritePut(options)
      : removePhotoFavoriteApiV1PhotosPhotoIdFavoriteDelete(options),
  )
}

export function getPhotoContentUrl(photoId: string): string {
  return `/api/v1/photos/${encodeURIComponent(photoId)}/content`
}

export function getPhotoDownloadUrl(photoId: string): string {
  return `/api/v1/photos/${encodeURIComponent(photoId)}/download`
}

export function getPhotoThumbnailUrl(photoId: string): string {
  return `/api/v1/photos/${encodeURIComponent(photoId)}/thumbnail`
}
