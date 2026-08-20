import { useEffect, useState, type PropsWithChildren } from 'react'
import { createPhotoMediaCache, type PhotoMediaCache } from './photoMediaCache'
import { PhotoMediaCacheContext } from './photoMediaCacheContext'

export function PhotoMediaCacheProvider({ children }: PropsWithChildren) {
  const [cache] = useState<PhotoMediaCache>(() => createPhotoMediaCache())

  useEffect(() => () => cache.clear(), [cache])

  return <PhotoMediaCacheContext.Provider value={cache}>{children}</PhotoMediaCacheContext.Provider>
}
