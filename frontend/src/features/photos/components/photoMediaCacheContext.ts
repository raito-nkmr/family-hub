import { createContext } from 'react'
import type { PhotoMediaCache } from './photoMediaCache'

export const PhotoMediaCacheContext = createContext<PhotoMediaCache | null>(null)
