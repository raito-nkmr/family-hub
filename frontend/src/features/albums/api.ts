import {
  addAlbumPhotosApiV1AlbumsAlbumIdPhotosPost,
  createAlbumApiV1AlbumsPost,
  deleteAlbumApiV1AlbumsAlbumIdDelete,
  getAlbumApiV1AlbumsAlbumIdGet,
  listAlbumsApiV1AlbumsGet,
  removeAlbumPhotoApiV1AlbumsAlbumIdPhotosPhotoIdDelete,
  updateAlbumApiV1AlbumsAlbumIdPatch,
  type AlbumCreate,
  type AlbumDetailResponse,
  type AlbumResponse,
  type AlbumUpdate,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type Album = AlbumResponse
export type AlbumDetail = AlbumDetailResponse
type AlbumInput = AlbumCreate
type AlbumChanges = AlbumUpdate

export async function getAlbums(signal?: AbortSignal): Promise<Album[]> {
  return (await sdkData(listAlbumsApiV1AlbumsGet({ signal }))).items
}

export function getAlbum(albumId: string, signal?: AbortSignal, cursor?: string): Promise<AlbumDetail> {
  return sdkData(getAlbumApiV1AlbumsAlbumIdGet({ path: { album_id: albumId }, query: { limit: 50, cursor }, signal }))
}

export function createAlbum(input: AlbumInput): Promise<Album> {
  return sdkData(createAlbumApiV1AlbumsPost({ body: input }))
}

export function updateAlbum(albumId: string, input: AlbumChanges): Promise<Album> {
  return sdkData(updateAlbumApiV1AlbumsAlbumIdPatch({ path: { album_id: albumId }, body: input }))
}

export function deleteAlbum(albumId: string): Promise<void> {
  return sdkData(deleteAlbumApiV1AlbumsAlbumIdDelete({ path: { album_id: albumId } }))
}

export function addPhotosToAlbum(albumId: string, photoIds: string[]): Promise<AlbumDetail> {
  return sdkData(
    addAlbumPhotosApiV1AlbumsAlbumIdPhotosPost({
      path: { album_id: albumId },
      body: { photo_ids: photoIds },
    }),
  )
}

export function removePhotoFromAlbum(albumId: string, photoId: string): Promise<void> {
  return sdkData(
    removeAlbumPhotoApiV1AlbumsAlbumIdPhotosPhotoIdDelete({
      path: { album_id: albumId, photo_id: photoId },
    }),
  )
}
