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
  load: (url: string) => Promise<{ objectUrl: string; cached: boolean }>
  release: (objectUrl: string) => void
  clear: () => void
}

export function createPhotoMediaCache(options: PhotoMediaCacheOptions = {}): PhotoMediaCache {
  const fetchMedia = options.fetchMedia ?? globalThis.fetch.bind(globalThis)
  const createObjectUrl = options.createObjectUrl ?? ((blob: Blob) => URL.createObjectURL(blob))
  const revokeObjectUrl = options.revokeObjectUrl ?? ((objectUrl: string) => URL.revokeObjectURL(objectUrl))
  const entries = new Map<string, PhotoMediaCacheEntry>()
  const pending = new Map<string, Promise<{ objectUrl: string; cached: boolean }>>()
  const temporaryObjectUrls = new Set<string>()
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

  const load = (url: string): Promise<{ objectUrl: string; cached: boolean }> => {
    const cached = get(url)
    if (cached) return Promise.resolve({ objectUrl: cached, cached: true })

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
        if (blob.size > MAX_CACHE_BYTES) {
          temporaryObjectUrls.add(objectUrl)
          return { objectUrl, cached: false }
        }
        const previous = entries.get(url)
        if (previous) {
          totalBytes -= previous.sizeBytes
          revokeObjectUrl(previous.objectUrl)
        }
        entries.set(url, { objectUrl, sizeBytes: blob.size, lastUsedAt: Date.now() })
        totalBytes += blob.size
        while (totalBytes > MAX_CACHE_BYTES && entries.size > 1) removeOldest()
        return { objectUrl, cached: true }
      })
      .finally(() => {
        if (pending.get(url) === request) pending.delete(url)
      })
    pending.set(url, request)
    return request
  }

  const release = (objectUrl: string) => {
    if (!temporaryObjectUrls.delete(objectUrl)) return
    revokeObjectUrl(objectUrl)
  }

  const clear = () => {
    generation += 1
    for (const entry of entries.values()) revokeObjectUrl(entry.objectUrl)
    for (const objectUrl of temporaryObjectUrls) revokeObjectUrl(objectUrl)
    entries.clear()
    temporaryObjectUrls.clear()
    pending.clear()
    totalBytes = 0
  }

  return { get, load, release, clear }
}
