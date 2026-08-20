import { describe, expect, it, vi } from 'vitest'
import { createPhotoMediaCache } from './photoMediaCache'

describe('createPhotoMediaCache', () => {
  it('deduplicates requests and reuses loaded media until the cache is cleared', async () => {
    const fetchMedia = vi.fn<typeof fetch>().mockResolvedValue(new Response('photo'))
    const createObjectUrl = vi.fn(() => 'blob:photo')
    const revokeObjectUrl = vi.fn()
    const cache = createPhotoMediaCache({ fetchMedia, createObjectUrl, revokeObjectUrl })

    const first = cache.load('/api/v1/photos/photo-1/content')
    const second = cache.load('/api/v1/photos/photo-1/content')

    await expect(first).resolves.toEqual({ objectUrl: 'blob:photo', cached: true })
    await expect(second).resolves.toEqual({ objectUrl: 'blob:photo', cached: true })
    expect(fetchMedia).toHaveBeenCalledOnce()
    expect(cache.get('/api/v1/photos/photo-1/content')).toBe('blob:photo')

    cache.clear()

    expect(cache.get('/api/v1/photos/photo-1/content')).toBeUndefined()
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:photo')
  })

  it('does not keep failed responses in the cache', async () => {
    const fetchMedia = vi.fn<typeof fetch>().mockResolvedValue(new Response('unavailable', { status: 503 }))
    const cache = createPhotoMediaCache({ fetchMedia, createObjectUrl: () => 'blob:photo' })

    await expect(cache.load('/api/v1/photos/photo-1/content')).rejects.toThrow()
    expect(cache.get('/api/v1/photos/photo-1/content')).toBeUndefined()
  })

  it('keeps an oversized image out of the cache until its temporary URL is released', async () => {
    const largeBlob = new Blob([new Uint8Array(64 * 1024 * 1024 + 1)])
    const fetchMedia = vi.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => largeBlob,
    } as Response)
    const revokeObjectUrl = vi.fn()
    const cache = createPhotoMediaCache({
      fetchMedia,
      createObjectUrl: () => 'blob:large-photo',
      revokeObjectUrl,
    })

    await expect(cache.load('/api/v1/photos/large/content')).resolves.toEqual({
      objectUrl: 'blob:large-photo',
      cached: false,
    })
    expect(cache.get('/api/v1/photos/large/content')).toBeUndefined()

    cache.release('blob:large-photo')

    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:large-photo')
  })
})
