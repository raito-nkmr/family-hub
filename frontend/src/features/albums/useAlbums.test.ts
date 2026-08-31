import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import {
  createAlbum,
  getAlbum,
  getAlbums,
  removePhotoFromAlbum,
  updateAlbum,
  type Album,
  type AlbumDetail,
} from './api'
import type { Photo } from '../photos/public'
import { useAlbums } from './useAlbums'
import { getGroups } from '../groups/api'

vi.mock('./api', () => ({
  addPhotosToAlbum: vi.fn(),
  createAlbum: vi.fn(),
  deleteAlbum: vi.fn(),
  getAlbum: vi.fn(),
  getAlbums: vi.fn(),
  removePhotoFromAlbum: vi.fn(),
  updateAlbum: vi.fn(),
}))
vi.mock('../groups/api', () => ({ getGroups: vi.fn() }))
vi.mock('../../shared/ui/confirmation', () => ({ useConfirmation: () => async () => true }))

const album: Album = {
  id: 'album-1',
  title: '北海道旅行',
  description: null,
  created_by_user_id: 'user-1',
  created_by_username: 'owner',
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T00:00:00Z',
  photo_count: 0,
  group_ids: ['group-1'],
  group_names: ['同居家族'],
  cover_photo_id: null,
}

const albumDetail: AlbumDetail = { ...album, photos: [], next_cursor: null }

describe('useAlbums', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getAlbums).mockResolvedValue([])
    vi.mocked(getGroups).mockResolvedValue([])
  })

  it('adds a newly created album and closes the dialog', async () => {
    vi.mocked(createAlbum).mockResolvedValue(album)
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useAlbums({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => result.current.openDialog('create'))
    await act(() => result.current.create({ title: album.title, description: null, group_ids: ['group-1'] }))

    expect(result.current.albums).toEqual([album])
    expect(result.current.showCreateDialog).toBe(false)
  })

  it('removes multiple selected photos and refreshes the album state', async () => {
    vi.mocked(getAlbums).mockResolvedValue([album])
    vi.mocked(getAlbum).mockResolvedValue(albumDetail)
    vi.mocked(removePhotoFromAlbum).mockResolvedValue()
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useAlbums({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.openAlbum(album))
    let removed = false
    await act(async () => {
      removed = await result.current.removePhotos(['photo-1', 'photo-2'])
    })

    expect(removed).toBe(true)
    expect(removePhotoFromAlbum).toHaveBeenCalledTimes(2)
    expect(removePhotoFromAlbum).toHaveBeenCalledWith(album.id, 'photo-1')
    expect(removePhotoFromAlbum).toHaveBeenCalledWith(album.id, 'photo-2')
    expect(result.current.removingPhotoIds.size).toBe(0)
    expect(result.current.selectedAlbum).toEqual(albumDetail)
  })

  it('updates the cover in the open album immediately', async () => {
    const coverPhoto = { id: 'photo-2' } as Photo
    const updatedAlbum = { ...album, cover_photo_id: coverPhoto.id }
    vi.mocked(getAlbum).mockResolvedValue(albumDetail)
    vi.mocked(updateAlbum).mockResolvedValue(updatedAlbum)
    const { result } = renderHook(() => useAlbums({ onUnauthorized: vi.fn() }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(() => result.current.openAlbum(album))

    let updated = false
    await act(async () => {
      updated = await result.current.setCover(coverPhoto)
    })

    expect(updated).toBe(true)
    await waitFor(() => expect(result.current.selectedAlbum?.cover_photo_id).toBe(coverPhoto.id))
  })

  it('restores the open album from the URL', async () => {
    vi.mocked(getAlbum).mockResolvedValue(albumDetail)
    const { result } = renderHook(() => useAlbums({ onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper('/albums?album=album-1'),
    })

    await waitFor(() => expect(result.current.selectedAlbum).toEqual(albumDetail))
    expect(getAlbum).toHaveBeenCalledWith(album.id, expect.any(AbortSignal), undefined)
  })

  it('loads additional album photos with the detail cursor', async () => {
    const firstPhoto = { id: 'photo-1' } as Photo
    const secondPhoto = { id: 'photo-2' } as Photo
    vi.mocked(getAlbum).mockImplementation((_albumId, _signal, cursor) =>
      Promise.resolve(
        cursor
          ? { ...albumDetail, photos: [secondPhoto], next_cursor: null, photo_count: 2 }
          : { ...albumDetail, photos: [firstPhoto], next_cursor: 'next-page', photo_count: 2 },
      ),
    )
    const { result } = renderHook(() => useAlbums({ onUnauthorized: vi.fn() }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.openAlbum(album))
    expect(result.current.selectedAlbum?.photos).toEqual([firstPhoto])
    await act(() => result.current.loadMore())

    await waitFor(() => expect(result.current.selectedAlbum?.photos).toEqual([firstPhoto, secondPhoto]))
    expect(getAlbum).toHaveBeenLastCalledWith(album.id, expect.any(AbortSignal), 'next-page')
  })

  it('keeps the most recently opened album when responses arrive out of order', async () => {
    const secondAlbum = { ...album, id: 'album-2', title: '沖縄旅行' }
    const secondDetail = { ...albumDetail, ...secondAlbum }
    let resolveFirst: ((value: AlbumDetail) => void) | undefined
    vi.mocked(getAlbum).mockImplementation((albumId) => {
      if (albumId === album.id) return new Promise((resolve) => (resolveFirst = resolve))
      return Promise.resolve(secondDetail)
    })
    const { result } = renderHook(() => useAlbums({ onUnauthorized: vi.fn() }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))

    let firstRequest: Promise<void>
    act(() => {
      firstRequest = result.current.openAlbum(album)
    })
    await act(() => result.current.openAlbum(secondAlbum))
    resolveFirst?.(albumDetail)
    await act(() => firstRequest!)

    expect(result.current.selectedAlbum).toEqual(secondDetail)
  })
})
