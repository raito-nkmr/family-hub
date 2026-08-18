import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PhotoPage } from './api'
import { getPhotos } from './api'
import { usePhotoList } from './usePhotoList'
import { createAppWrapper } from '../../test/renderWithAppProviders'

vi.mock('./api', () => ({
  getPhotos: vi.fn(),
}))

const page = (ids: string[], nextCursor: string | null): PhotoPage =>
  ({
    items: ids.map((id) => ({ id })),
    total_count: 3,
    next_cursor: nextCursor,
  }) as unknown as PhotoPage

describe('usePhotoList', () => {
  it('shares cursor pagination and retries failed next pages', async () => {
    vi.mocked(getPhotos)
      .mockResolvedValueOnce(page(['photo-1'], 'next-cursor'))
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce(page(['photo-2', 'photo-3'], null))
    const filters = { excludeAlbumId: 'album-1', sharingGroupId: 'group-1' }
    const { result } = renderHook(() => usePhotoList({ filters }), { wrapper: createAppWrapper() })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.photos).toHaveLength(1)
    expect(result.current.hasMore).toBe(true)

    await act(() => result.current.loadMore())
    await waitFor(() => expect(result.current.loadMoreFailed).toBe(true))
    expect(result.current.photos).toHaveLength(1)

    await act(() => result.current.loadMore())
    await waitFor(() => expect(result.current.hasMore).toBe(false))
    expect(result.current.photos.map(({ id }) => id)).toEqual(['photo-1', 'photo-2', 'photo-3'])
    expect(getPhotos).toHaveBeenNthCalledWith(1, filters, undefined, expect.any(AbortSignal))
    expect(getPhotos).toHaveBeenNthCalledWith(2, filters, 'next-cursor', expect.any(AbortSignal))
    expect(getPhotos).toHaveBeenNthCalledWith(3, filters, 'next-cursor', expect.any(AbortSignal))
  })

  it('starts a new cached query when search filters change', async () => {
    vi.mocked(getPhotos).mockResolvedValue(page(['photo-1'], null))
    const { result, rerender } = renderHook(({ filters }) => usePhotoList({ filters }), {
      initialProps: { filters: { q: 'first' } },
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    rerender({ filters: { q: 'second' } })
    await waitFor(() => expect(getPhotos).toHaveBeenCalledWith({ q: 'second' }, undefined, expect.any(AbortSignal)))
  })
})
