import { useContext, useEffect, useState } from 'react'
import { PhotoMediaCacheContext } from './photoMediaCacheContext'

export function useCachedPhotoMediaUrl(url: string, enabled: boolean) {
  const cache = useContext(PhotoMediaCacheContext)
  const shouldCache = enabled && cache !== null
  const [state, setState] = useState<{ url: string; objectUrl: string; failed: boolean } | null>(null)
  const cachedUrl = shouldCache ? cache.get(url) : undefined
  const currentState = state?.url === url ? state : null

  useEffect(() => {
    if (!shouldCache || !cache || cache.get(url)) return
    let active = true
    void cache
      .load(url)
      .then((objectUrl) => {
        if (active) setState({ url, objectUrl, failed: false })
      })
      .catch(() => {
        if (active) setState({ url, objectUrl: '', failed: true })
      })
    return () => {
      active = false
    }
  }, [cache, shouldCache, url])

  if (!shouldCache) return { url, loading: false, failed: false }
  return {
    url: currentState?.objectUrl || cachedUrl || null,
    loading: currentState === null && cachedUrl === undefined,
    failed: currentState?.failed === true,
  }
}
