import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { ApiError } from '../../shared/api/client'
import {
  addBulkPhotoSharing,
  cancelUploadBatch,
  completeUploadItem,
  createUploadBatch,
  getPhoto,
  getPhotos,
  getPhotoTimeline,
  getStorageStatus,
  getUploadBatch,
  updatePhoto,
  uploadItemContent,
  type Photo,
  type StorageStatus,
  type UploadBatch,
  type UploadItem,
} from './api'
import { usePhotoDashboard } from './usePhotoDashboard'
import { getGroups } from '../groups/api'
import { useHome } from '../home/useHome'

vi.mock('./api', () => ({
  addBulkPhotoSharing: vi.fn(),
  getPhotos: vi.fn(),
  getPhoto: vi.fn(),
  getPhotoTimeline: vi.fn(),
  getStorageStatus: vi.fn(),
  updatePhoto: vi.fn(),
  createUploadBatch: vi.fn(),
  getUploadBatch: vi.fn(),
  completeUploadItem: vi.fn(),
  uploadItemContent: vi.fn(),
  cancelUploadBatch: vi.fn(),
  setPhotoFavorite: vi.fn(),
}))
vi.mock('../groups/api', () => ({ getGroups: vi.fn() }))

const storage: StorageStatus = {
  status: 'available',
  available: true,
  writable: true,
  free_bytes: 1024,
  minimum_free_bytes: 128,
  total_bytes: 2048,
}

const photo: Photo = {
  id: 'photo-1',
  uploaded_by_user_id: 'user-1',
  uploaded_by_username: 'owner',
  visibility: 'private',
  sharing: { type: 'private', group_ids: [] },
  is_favorite: false,
  memo: null,
  memo_updated_by_user_id: 'user-1',
  memo_updated_by_username: 'owner',
  memo_updated_at: '2026-07-15T00:00:00Z',
  metadata_version: 1,
  original_filename: 'photo.jpg',
  storage_key: 'originals/2026/07/photo-1.jpg',
  content_type: 'image/jpeg',
  size_bytes: 5,
  sha256: 'a'.repeat(64),
  width: 100,
  height: 100,
  captured_at: null,
  uploaded_at: '2026-07-15T00:00:00Z',
  lifecycle_state: 'active',
  trashed_at: null,
  purge_after: null,
  purge_requested_at: null,
}

const uploadItems: UploadItem[] = ['first', 'second'].map((clientId) => ({
  id: `00000000-0000-4000-8000-00000000000${clientId === 'first' ? '1' : '2'}`,
  client_id: clientId,
  filename: `${clientId}.jpg`,
  content_type: 'image/jpeg',
  size_bytes: 5,
  received_bytes: 0,
  status: 'queued',
  error_code: null,
  photo_id: null,
}))

const uploadBatch: UploadBatch = {
  id: '00000000-0000-4000-8000-000000000010',
  status: 'active',
  visibility: 'private',
  created_at: '2026-07-15T00:00:00Z',
  expires_at: '2026-07-16T00:00:00Z',
  completed_at: null,
  group_ids: [],
  items: uploadItems,
}

describe('usePhotoDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getStorageStatus).mockResolvedValue(storage)
    vi.mocked(getPhotos).mockResolvedValue({ items: [photo], next_cursor: null, total_count: 1 })
    vi.mocked(getPhoto).mockResolvedValue(photo)
    vi.mocked(getPhotoTimeline).mockImplementation(async (year) => ({
      year,
      months: [{ month: `${year}-07`, count: 1 }],
    }))
    vi.mocked(getGroups).mockResolvedValue([])
  })

  it('loads storage and photos when a session becomes available', async () => {
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.storage).toEqual(storage)
    expect(result.current.photos).toEqual([photo])
    expect(result.current.totalCount).toBe(1)
  })

  it('does not load photo groups when the dashboard is outside photo and home screens', async () => {
    const { result } = renderHook(
      () =>
        usePhotoDashboard({
          enabled: true,
          libraryEnabled: false,
          storageEnabled: true,
          groupsEnabled: false,
          onUnauthorized: vi.fn(),
        }),
      { wrapper: createAppWrapper() },
    )

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(getGroups).not.toHaveBeenCalled()
  })

  it('loads the next cursor page without replacing existing photos', async () => {
    const secondPhoto = { ...photo, id: 'photo-2', original_filename: 'second.jpg' }
    vi.mocked(getPhotos)
      .mockReset()
      .mockResolvedValueOnce({ items: [photo], next_cursor: 'page-2', total_count: 2 })
      .mockResolvedValueOnce({ items: [secondPhoto], next_cursor: null, total_count: 2 })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.hasMore).toBe(true)

    await act(() => result.current.loadMore())

    expect(getPhotos).toHaveBeenLastCalledWith({}, 'page-2', expect.any(AbortSignal))
    await waitFor(() => expect(result.current.photos.map(({ id }) => id)).toEqual(['photo-1', 'photo-2']))
    expect(result.current.hasMore).toBe(false)
  })

  it('exposes adjacent library photos for detail navigation', async () => {
    const secondPhoto = { ...photo, id: 'photo-2', original_filename: 'second.jpg' }
    const thirdPhoto = { ...photo, id: 'photo-3', original_filename: 'third.jpg' }
    vi.mocked(getPhotos).mockResolvedValue({
      items: [photo, secondPhoto, thirdPhoto],
      next_cursor: null,
      total_count: 3,
    })
    vi.mocked(getPhoto).mockImplementation(
      async (photoId) => [photo, secondPhoto, thirdPhoto].find(({ id }) => id === photoId) ?? photo,
    )
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.selectPhoto(secondPhoto))

    expect(result.current.previousPhoto?.id).toBe('photo-1')
    expect(result.current.nextPhoto?.id).toBe('photo-3')
  })

  it('keeps the current detail while the next photo loads', async () => {
    const secondPhoto = { ...photo, id: 'photo-2', original_filename: 'second.jpg' }
    let resolveSecond: ((value: Photo) => void) | undefined
    vi.mocked(getPhoto).mockImplementation(async (photoId) => {
      if (photoId === secondPhoto.id) {
        return new Promise((resolve) => {
          resolveSecond = resolve
        })
      }
      return photo
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.selectPhoto(photo))
    let secondRequest!: Promise<void>
    act(() => {
      secondRequest = result.current.selectPhoto(secondPhoto)
    })

    await waitFor(() => expect(result.current.selectedPhoto?.id).toBe(photo.id))
    resolveSecond?.(secondPhoto)
    await act(() => secondRequest)

    await waitFor(() => expect(result.current.selectedPhoto?.id).toBe(secondPhoto.id))
  })

  it('shows a detail error without exposing stale content and retries the selected photo', async () => {
    const secondPhoto = { ...photo, id: 'photo-2', original_filename: 'second.jpg' }
    let shouldFail = true
    vi.mocked(getPhoto).mockImplementation(async (photoId) => {
      if (photoId === secondPhoto.id && shouldFail) throw new Error('unavailable')
      return photoId === secondPhoto.id ? secondPhoto : photo
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.selectPhoto(photo))
    await act(() => result.current.selectPhoto(secondPhoto))

    expect(result.current.selectedPhoto?.id).toBe(photo.id)
    expect(result.current.photoDetailError).toBe('写真の詳細を取得できませんでした。')

    shouldFail = false
    await act(() => result.current.retryPhotoDetail())

    await waitFor(() => expect(result.current.selectedPhoto?.id).toBe(secondPhoto.id))
    expect(result.current.photoDetailError).toBeNull()
  })

  it('ignores an old cursor page that completes after a new search', async () => {
    const oldPagePhoto = { ...photo, id: 'old-page-photo' }
    const searchedPhoto = { ...photo, id: 'searched-photo' }
    let resolveOldPage: ((value: Awaited<ReturnType<typeof getPhotos>>) => void) | undefined
    vi.mocked(getPhotos)
      .mockReset()
      .mockImplementation(async (filters, cursor) => {
        if (cursor === 'page-2') return new Promise((resolve) => (resolveOldPage = resolve))
        if (filters?.q === 'new') return { items: [searchedPhoto], next_cursor: null, total_count: 1 }
        return { items: [photo], next_cursor: 'page-2', total_count: 2 }
      })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    let oldRequest: Promise<void>
    act(() => {
      oldRequest = result.current.loadMore()
    })
    await act(() => result.current.search({ q: 'new' }))
    resolveOldPage?.({ items: [oldPagePhoto], next_cursor: null, total_count: 2 })
    await act(() => oldRequest!)

    expect(result.current.photos).toEqual([searchedPhoto])
  })

  it('keeps the selected timeline year when filtering photos', async () => {
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.changeTimelineYear(2025))
    await act(() => result.current.search({ dateFrom: '2025-07-01', dateTo: '2025-07-31' }))

    expect(getPhotoTimeline).toHaveBeenLastCalledWith(2025, expect.any(AbortSignal))
    expect(result.current.timeline?.year).toBe(2025)
  })

  it('clears transient dashboard state when the session is reset', async () => {
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.selectPhoto(photo)
      result.current.selectFiles([new File(['photo'], 'private.jpg', { type: 'image/jpeg' })])
    })
    expect(result.current.selectedPhoto).toEqual(photo)
    expect(result.current.uploadQueue).toHaveLength(1)

    act(() => result.current.reset())

    expect(result.current.selectedPhoto).toBeNull()
    expect(result.current.uploadQueue).toEqual([])
  })

  it('restores photo filters and timeline year from the URL', async () => {
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper('/photos?q=summer&favorite=1&year=2024'),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.photoFilters).toEqual({ q: 'summer', favorite: true })
    expect(result.current.timeline?.year).toBe(2024)
    expect(getPhotos).toHaveBeenCalledWith({ q: 'summer', favorite: true }, undefined, expect.any(AbortSignal))
  })

  it('keeps the most recently selected photo when responses arrive out of order', async () => {
    const secondPhoto = { ...photo, id: 'photo-2', original_filename: 'second.jpg' }
    let resolveFirst: ((value: Photo) => void) | undefined
    vi.mocked(getPhoto).mockImplementation((photoId) => {
      if (photoId === photo.id) return new Promise((resolve) => (resolveFirst = resolve))
      return Promise.resolve(secondPhoto)
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    let firstRequest: Promise<void>
    act(() => {
      firstRequest = result.current.selectPhoto(photo)
    })
    await act(() => result.current.selectPhoto(secondPhoto))
    resolveFirst?.(photo)
    await act(() => firstRequest!)

    expect(result.current.selectedPhoto).toEqual(secondPhoto)
  })

  it('uploads multiple selected files and refreshes the dashboard', async () => {
    vi.mocked(createUploadBatch).mockImplementation(async (files) => ({
      ...uploadBatch,
      items: uploadItems.map((item, index) => ({ ...item, client_id: files[index].client_id })),
    }))
    vi.mocked(uploadItemContent).mockImplementation(async (_item, file, _signal, onProgress) => {
      onProgress(file.size)
    })
    vi.mocked(completeUploadItem).mockImplementation(async (itemId) => ({
      ...uploadItems.find((item) => item.id === itemId)!,
      received_bytes: 5,
      status: 'succeeded',
      photo_id: itemId,
    }))
    vi.mocked(getUploadBatch).mockResolvedValue({ ...uploadBatch, status: 'completed' })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => {
      result.current.changeUploadGroups(['group-1'])
      result.current.selectFiles([
        new File(['photo'], 'first.jpg', { type: 'image/jpeg' }),
        new File(['photo'], 'second.jpeg'),
      ])
    })
    await act(() => result.current.upload())

    expect(createUploadBatch).toHaveBeenCalledWith(
      [
        expect.objectContaining({ filename: 'first.jpg', content_type: 'image/jpeg' }),
        expect.objectContaining({ filename: 'second.jpeg', content_type: 'image/jpeg' }),
      ],
      ['group-1'],
    )
    expect(uploadItemContent).toHaveBeenCalledTimes(2)
    expect(result.current.uploadMessage).toEqual({ type: 'success', text: '2枚を保存しました。' })
    expect(result.current.uploadQueue.every((item) => item.status === 'succeeded')).toBe(true)
    expect(result.current.uploadQueue.map((item) => item.photoId)).toEqual(uploadItems.map((item) => item.id))
  })

  it('cancels a batch that finishes being created after the user cancels', async () => {
    let resolveBatch: ((value: UploadBatch) => void) | undefined
    vi.mocked(createUploadBatch).mockImplementation(
      (files) =>
        new Promise((resolve) => {
          resolveBatch = (batch) =>
            resolve({
              ...batch,
              items: [{ ...uploadItems[0], client_id: files[0].client_id }],
            })
        }),
    )
    vi.mocked(cancelUploadBatch).mockResolvedValue()
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))
    act(() => result.current.selectFiles([new File(['photo'], 'first.jpg', { type: 'image/jpeg' })]))

    let uploadPromise: Promise<void>
    act(() => {
      uploadPromise = result.current.upload()
    })
    await waitFor(() => expect(createUploadBatch).toHaveBeenCalledOnce())
    await act(() => result.current.cancelUpload())
    resolveBatch?.(uploadBatch)
    await act(() => uploadPromise!)

    expect(cancelUploadBatch).toHaveBeenCalledWith(uploadBatch.id)
    expect(uploadItemContent).not.toHaveBeenCalled()
    expect(result.current.uploadQueue[0]).toMatchObject({ status: 'failed', errorCode: 'canceled' })
  })

  it('adds sharing to multiple photos and refreshes the dashboard', async () => {
    vi.mocked(addBulkPhotoSharing).mockResolvedValue({
      operation_id: 'operation-1',
      updated_count: 2,
      unchanged_count: 0,
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.bulkAddSharing(['photo-1', 'photo-2'], ['group-1']))

    expect(addBulkPhotoSharing).toHaveBeenCalledWith(['photo-1', 'photo-2'], ['group-1'])
    expect(getPhotos).toHaveBeenCalledTimes(2)
  })

  it('invalidates the home recent photos after a photo change', async () => {
    vi.mocked(addBulkPhotoSharing).mockResolvedValue({
      operation_id: 'operation-1',
      updated_count: 1,
      unchanged_count: 0,
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(
      () => ({
        dashboard: usePhotoDashboard({ enabled: true, onUnauthorized }),
        home: useHome({ userId: 'user-1', active: true, onUnauthorized }),
      }),
      { wrapper: createAppWrapper() },
    )
    await waitFor(() => expect(result.current.dashboard.loading).toBe(false))
    await waitFor(() => expect(result.current.home.loading).toBe(false))
    const homeCallsBeforeChange = vi.mocked(getPhotos).mock.calls.filter(([, , , limit]) => limit === 4).length

    await act(() => result.current.dashboard.bulkAddSharing(['photo-1'], ['group-1']))

    await waitFor(() =>
      expect(vi.mocked(getPhotos).mock.calls.filter(([, , , limit]) => limit === 4).length).toBeGreaterThan(
        homeCallsBeforeChange,
      ),
    )
  })

  it('saves a photo memo with optimistic metadata versioning', async () => {
    vi.mocked(updatePhoto).mockResolvedValue({ ...photo, memo: '北海道旅行', metadata_version: 2 })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.selectPhoto(photo))
    await act(() => result.current.savePhotoMetadata({ memo: '北海道旅行' }))

    expect(updatePhoto).toHaveBeenCalledWith('photo-1', { memo: '北海道旅行', version: 1 })
    expect(result.current.selectedPhoto?.memo).toBe('北海道旅行')
    expect(result.current.selectedPhoto?.metadata_version).toBe(2)
  })

  it('notifies the app when loading finds an expired session', async () => {
    vi.mocked(getPhotos).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()

    renderHook(() => usePhotoDashboard({ enabled: true, onUnauthorized }), { wrapper: createAppWrapper() })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
    expect(updatePhoto).not.toHaveBeenCalled()
  })
})
