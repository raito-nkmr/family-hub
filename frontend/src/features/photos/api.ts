import { ApiError, csrfHeaders } from '../../shared/api/client'
import type {
  BulkPhotoSharingResponse,
  BulkPhotoSharingAdd,
  PhotoListResponse,
  PhotoListItemResponse,
  PhotoActivityResponse,
  PhotoActivitySeenUpdate,
  PhotoActivityItemResponse,
  PhotoResponse,
  PhotoSearchOptionsResponse,
  PhotoTimelineResponse,
  PhotoUpdate,
  PhotoVisibility as ApiPhotoVisibility,
  StorageStatusCode as ApiStorageStatusCode,
  StorageStatusResponse,
  TrashedPhotoListResponse,
  UploadBatchResponse,
  UploadBatchCreate,
  UploadItemResponse,
} from '../../shared/api/generated'
import {
  addPhotoFavoriteApiV1PhotosPhotoIdFavoritePut,
  bulkAddPhotoSharingApiV1PhotosBulkSharingPost,
  cancelUploadBatchApiV1UploadBatchesBatchIdDelete,
  completeUploadItemApiV1UploadBatchesItemsItemIdCompletePost,
  createUploadBatchApiV1UploadBatchesPost,
  getPhotoMetadataApiV1PhotosPhotoIdGet,
  getPhotoSearchOptionsApiV1PhotosSearchOptionsGet,
  getPhotoTimelineApiV1PhotosTimelineGet,
  getStorageStatusApiV1PhotosStorageStatusGet,
  getUploadBatchApiV1UploadBatchesBatchIdGet,
  listPhotoActivityApiV1PhotosActivityGet,
  listPhotoMetadataApiV1PhotosGet,
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
export type UploadBatch = UploadBatchResponse
export type UploadItem = UploadItemResponse
export type TrashedPhotoList = TrashedPhotoListResponse

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
    listPhotoMetadataApiV1PhotosGet({
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
  return sdkData(getPhotoMetadataApiV1PhotosPhotoIdGet({ path: { photo_id: photoId }, signal }))
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
  const body: BulkPhotoSharingAdd = { photo_ids: photoIds, add_group_ids: groupIds }
  return sdkData(bulkAddPhotoSharingApiV1PhotosBulkSharingPost({ body }))
}

export function getPhotoExportUrl(photoIds: string[]): string {
  const params = new URLSearchParams()
  photoIds.forEach((photoId) => params.append('photo_ids', photoId))
  return `/api/v1/photos/export?${params}`
}

export function createUploadBatch(
  files: Array<{ client_id: string; filename: string; content_type: string; size_bytes: number }>,
  groupIds: string[],
): Promise<UploadBatch> {
  const body: UploadBatchCreate = {
    files,
    sharing: { type: groupIds.length > 0 ? 'shared' : 'private', group_ids: groupIds },
  }
  return sdkData(createUploadBatchApiV1UploadBatchesPost({ body }))
}

export function getUploadBatch(batchId: string): Promise<UploadBatch> {
  return sdkData(getUploadBatchApiV1UploadBatchesBatchIdGet({ path: { batch_id: batchId } }))
}

export function completeUploadItem(itemId: string): Promise<UploadItem> {
  return sdkData(completeUploadItemApiV1UploadBatchesItemsItemIdCompletePost({ path: { item_id: itemId } }))
}

export function cancelUploadBatch(batchId: string): Promise<void> {
  return sdkData(cancelUploadBatchApiV1UploadBatchesBatchIdDelete({ path: { batch_id: batchId } }))
}

const NETWORK_CHUNK_BYTES = 4 * 1024 * 1024

function readUploadOffset(response: Response): number {
  const value = response.headers.get('Upload-Offset')
  if (value === null || !/^\d+$/.test(value)) {
    throw new ApiError(response.status, 'Upload response did not include a valid offset')
  }
  return Number(value)
}

async function getUploadOffset(itemId: string, signal: AbortSignal): Promise<number> {
  const response = await fetch(`/api/v1/upload-batches/items/${encodeURIComponent(itemId)}/content`, {
    method: 'HEAD',
    credentials: 'include',
    cache: 'no-store',
    signal,
  })
  if (!response.ok) throw new ApiError(response.status, 'Could not read upload offset')
  return readUploadOffset(response)
}

async function sendUploadChunk(itemId: string, offset: number, chunk: Blob, signal: AbortSignal): Promise<number> {
  const response = await fetch(`/api/v1/upload-batches/items/${encodeURIComponent(itemId)}/content`, {
    method: 'PATCH',
    credentials: 'same-origin',
    headers: {
      ...csrfHeaders(),
      'Content-Type': 'application/offset+octet-stream',
      'Upload-Offset': String(offset),
    },
    body: chunk,
    signal,
  })
  if (response.status !== 204) throw new ApiError(response.status, `Upload failed with status ${response.status}`)
  return readUploadOffset(response)
}

export async function uploadItemContent(
  item: UploadItem,
  file: File,
  signal: AbortSignal,
  onProgress: (uploadedBytes: number) => void,
): Promise<void> {
  let offset = await getUploadOffset(item.id, signal)
  if (offset > file.size) throw new ApiError(409, 'Stored upload exceeds the selected file')
  onProgress(offset)
  while (offset < file.size) {
    const chunk = file.slice(offset, Math.min(offset + NETWORK_CHUNK_BYTES, file.size))
    if (chunk.size === 0) throw new ApiError(409, 'Selected file could not be read')
    const nextOffset = await sendUploadChunk(item.id, offset, chunk, signal)
    if (nextOffset <= offset || nextOffset > file.size) {
      throw new ApiError(409, 'Upload did not advance to a valid offset')
    }
    offset = nextOffset
    onProgress(offset)
  }
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
