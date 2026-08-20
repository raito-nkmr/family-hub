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

    await expect(first).resolves.toBe('blob:photo')
    await expect(second).resolves.toBe('blob:photo')
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
})
