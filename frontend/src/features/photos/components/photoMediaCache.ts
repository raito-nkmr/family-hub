const MAX_CACHE_BYTES = 64 * 1024 * 1024

interface PhotoMediaCacheEntry {
  objectUrl: string
  sizeBytes: number
  lastUsedAt: number
}

interface PhotoMediaCacheOptions {
  fetchMedia?: typeof fetch
  createObjectUrl?: (blob: Blob) => string
  revokeObjectUrl?: (objectUrl: string) => void
}

export interface PhotoMediaCache {
  get: (url: string) => string | undefined
  load: (url: string) => Promise<string>
  clear: () => void
}

export function createPhotoMediaCache(options: PhotoMediaCacheOptions = {}): PhotoMediaCache {
  const fetchMedia = options.fetchMedia ?? globalThis.fetch.bind(globalThis)
  const createObjectUrl = options.createObjectUrl ?? ((blob: Blob) => URL.createObjectURL(blob))
  const revokeObjectUrl = options.revokeObjectUrl ?? ((objectUrl: string) => URL.revokeObjectURL(objectUrl))
  const entries = new Map<string, PhotoMediaCacheEntry>()
  const pending = new Map<string, Promise<string>>()
  let totalBytes = 0
  let generation = 0

  const get = (url: string) => {
    const entry = entries.get(url)
    if (!entry) return undefined
    entry.lastUsedAt = Date.now()
    return entry.objectUrl
  }

  const removeOldest = () => {
    const oldest = [...entries.entries()].reduce<[string, PhotoMediaCacheEntry] | null>(
      (current, entry) => (!current || entry[1].lastUsedAt < current[1].lastUsedAt ? entry : current),
      null,
    )
    if (!oldest) return
    entries.delete(oldest[0])
    totalBytes -= oldest[1].sizeBytes
    revokeObjectUrl(oldest[1].objectUrl)
  }

  const load = (url: string): Promise<string> => {
    const cached = get(url)
    if (cached) return Promise.resolve(cached)

    const existingRequest = pending.get(url)
    if (existingRequest) return existingRequest

    const requestGeneration = generation
    const request = fetchMedia(url, { credentials: 'include' })
      .then((response) => {
        if (!response.ok) throw new Error(`Could not load photo media (${response.status})`)
        return response.blob()
      })
      .then((blob) => {
        const objectUrl = createObjectUrl(blob)
        if (requestGeneration !== generation) {
          revokeObjectUrl(objectUrl)
          throw new Error('Photo media cache was cleared')
        }
        const previous = entries.get(url)
        if (previous) {
          totalBytes -= previous.sizeBytes
          revokeObjectUrl(previous.objectUrl)
        }
        entries.set(url, { objectUrl, sizeBytes: blob.size, lastUsedAt: Date.now() })
        totalBytes += blob.size
        while (totalBytes > MAX_CACHE_BYTES && entries.size > 1) removeOldest()
        return objectUrl
      })
      .finally(() => {
        pending.delete(url)
      })
    pending.set(url, request)
    return request
  }

  const clear = () => {
    generation += 1
    for (const entry of entries.values()) revokeObjectUrl(entry.objectUrl)
    entries.clear()
    pending.clear()
    totalBytes = 0
  }

  return { get, load, clear }
}
