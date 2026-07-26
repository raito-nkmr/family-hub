import type { PhotoFilters, PhotoVisibility } from './api'

const filterKeys = [
  'q',
  'from',
  'to',
  'uploader',
  'mine',
  'visibility',
  'captured',
  'album',
  'excludeAlbum',
  'group',
  'favorite',
]

export function readPhotoSearchParams(params: URLSearchParams): PhotoFilters {
  const visibility = params.get('visibility')
  const captured = params.get('captured')
  return compactFilters({
    q: params.get('q') ?? undefined,
    dateFrom: params.get('from') ?? undefined,
    dateTo: params.get('to') ?? undefined,
    uploaderId: params.get('uploader') ?? undefined,
    mineOnly: params.get('mine') === '1' || undefined,
    visibility: visibility === 'private' || visibility === 'shared' ? (visibility as PhotoVisibility) : undefined,
    capturedAtKnown: captured === 'known' ? true : captured === 'unknown' ? false : undefined,
    albumId: params.get('album') ?? undefined,
    excludeAlbumId: params.get('excludeAlbum') ?? undefined,
    sharingGroupId: params.get('group') ?? undefined,
    favorite: params.get('favorite') === '1' || undefined,
  })
}

export function writePhotoSearchParams(current: URLSearchParams, filters: PhotoFilters): URLSearchParams {
  const next = new URLSearchParams(current)
  filterKeys.forEach((key) => next.delete(key))
  set(next, 'q', filters.q?.trim())
  set(next, 'from', filters.dateFrom)
  set(next, 'to', filters.dateTo)
  set(next, 'uploader', filters.uploaderId)
  set(next, 'mine', filters.mineOnly ? '1' : undefined)
  set(next, 'visibility', filters.visibility)
  set(
    next,
    'captured',
    filters.capturedAtKnown === true ? 'known' : filters.capturedAtKnown === false ? 'unknown' : undefined,
  )
  set(next, 'album', filters.albumId)
  set(next, 'excludeAlbum', filters.excludeAlbumId)
  set(next, 'group', filters.sharingGroupId)
  set(next, 'favorite', filters.favorite ? '1' : undefined)
  return next
}

export function readTimelineYear(params: URLSearchParams, fallback: number): number {
  const value = Number(params.get('year'))
  return Number.isInteger(value) && value >= 1 && value <= 9998 ? value : fallback
}

function compactFilters(filters: PhotoFilters): PhotoFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''))
}

function set(params: URLSearchParams, key: string, value: string | undefined) {
  if (value) params.set(key, value)
}
