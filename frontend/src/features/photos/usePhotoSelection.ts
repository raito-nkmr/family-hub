import { useCallback, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import i18n from '../../i18n'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { getPhoto, type Photo, type PhotoListItem } from './api'

interface UsePhotoSelectionOptions {
  photos: PhotoListItem[]
  onUnauthorized: () => void
}

export function usePhotoSelection({ photos, onUnauthorized }: UsePhotoSelectionOptions) {
  const queryClient = useQueryClient()
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(null)
  const [selectedPhotoSummary, setSelectedPhotoSummary] = useState<PhotoListItem | null>(null)
  const [photoDetailError, setPhotoDetailError] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)
  const photoDetailRequestIdRef = useRef(0)
  const detailQuery = useQuery({
    queryKey: queryKeys.photo(selectedPhotoId ?? ''),
    queryFn: ({ signal }) => getPhoto(selectedPhotoId!, signal),
    enabled: selectedPhotoId !== null,
  })

  useUnauthorizedError(detailQuery.error, onUnauthorized)

  const selectedPhoto = selectedPhotoId !== null && detailQuery.data?.id === selectedPhotoId ? detailQuery.data : null
  const selectedPhotoIndex = photos.findIndex((photo) => photo.id === selectedPhotoId)
  const previousPhoto = selectedPhotoIndex > 0 ? photos[selectedPhotoIndex - 1] : null
  const nextPhoto = selectedPhotoIndex >= 0 ? (photos[selectedPhotoIndex + 1] ?? null) : null

  const loadPhotoDetail = useCallback(
    async (photoId: string, showPageError: boolean, requestId: number) => {
      try {
        await queryClient.fetchQuery({
          queryKey: queryKeys.photo(photoId),
          queryFn: ({ signal }) => getPhoto(photoId, signal),
        })
        if (requestId !== photoDetailRequestIdRef.current) return
        setPhotoDetailError(null)
        setPageError(null)
      } catch (error) {
        if (requestId !== photoDetailRequestIdRef.current) return
        if (isUnauthorizedError(error)) {
          setPhotoDetailError(null)
          onUnauthorized()
        } else {
          const message = i18n.t('photos.detailFailed')
          setPhotoDetailError(message)
          if (showPageError) setPageError(message)
        }
      }
    },
    [onUnauthorized, queryClient],
  )

  const selectPhoto = async (photo: Photo | PhotoListItem) => {
    const requestId = ++photoDetailRequestIdRef.current
    const hadSelectedPhoto = selectedPhotoId !== null
    setSelectedPhotoId(photo.id)
    setSelectedPhotoSummary(toPhotoListItem(photo))
    setPageError(null)
    setPhotoDetailError(null)
    await loadPhotoDetail(photo.id, !hadSelectedPhoto, requestId)
  }

  const retryPhotoDetail = async () => {
    if (selectedPhotoId === null) return
    const requestId = ++photoDetailRequestIdRef.current
    await loadPhotoDetail(selectedPhotoId, false, requestId)
  }

  const closePhoto = useCallback(() => {
    photoDetailRequestIdRef.current += 1
    setPhotoDetailError(null)
    setPageError(null)
    setSelectedPhotoId(null)
    setSelectedPhotoSummary(null)
  }, [])

  const reset = useCallback(() => {
    closePhoto()
  }, [closePhoto])

  return {
    selectedPhoto,
    selectedPhotoSummary,
    photoDetailLoading: detailQuery.isFetching,
    photoDetailError,
    photoDetailPageError: pageError,
    retryPhotoDetail,
    previousPhoto,
    nextPhoto,
    selectPhoto,
    closePhoto,
    reset,
  }
}

function toPhotoListItem(photo: Photo | PhotoListItem): PhotoListItem {
  return {
    captured_at_original: photo.captured_at_original,
    captured_at_override: photo.captured_at_override,
    content_type: photo.content_type,
    effective_captured_at: photo.effective_captured_at,
    height: photo.height,
    id: photo.id,
    is_favorite: photo.is_favorite,
    original_filename: photo.original_filename,
    uploaded_at: photo.uploaded_at,
    uploaded_by_user_id: photo.uploaded_by_user_id,
    uploaded_by_username: photo.uploaded_by_username,
    visibility: photo.visibility,
    width: photo.width,
  }
}
