import { useCallback, useRef, useState } from 'react'
import i18n from '../../i18n'
import { isAbortError, isUnauthorizedError } from '../../shared/api/errors'
import { createClientId } from '../../shared/lib/uuid'
import {
  cancelUploadBatch,
  completeUploadItem,
  createUploadBatch,
  getUploadBatch,
  uploadItemContent,
} from './uploadApi'
import type { StorageStatus } from './api'
import type { UploadMessage } from './components/PhotoUploadCard'
import { getPhotoContentType } from './contentType'
import { getUploadErrorMessage } from './errors'
import type { QueuedUpload } from './uploadTypes'

const MAX_FILES_PER_BATCH = 100

interface PhotoUploadOptions {
  storage: StorageStatus | null
  onUploaded: () => Promise<void>
  onUnauthorized: () => void
}

export function usePhotoUpload({ storage, onUploaded, onUnauthorized }: PhotoUploadOptions) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadQueue, setUploadQueue] = useState<QueuedUpload[]>([])
  const [uploadGroupIds, setUploadGroupIds] = useState<string[]>([])
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState<UploadMessage | null>(null)
  const uploadControllerRef = useRef<AbortController | null>(null)
  const abandonedBatchRef = useRef<Promise<void> | null>(null)

  const upload = async () => {
    const eligible = uploadQueue.filter(
      (item) => !['succeeded', 'duplicate'].includes(item.status) && item.errorCode !== 'invalid_photo',
    )
    if (eligible.length === 0 || uploading || !storage?.available) return
    const controller = new AbortController()
    uploadControllerRef.current = controller
    setUploading(true)
    setUploadMessage(null)
    try {
      await abandonedBatchRef.current
      if (controller.signal.aborted) return
      let batch = activeBatchId ? await getUploadBatch(activeBatchId) : null
      if (controller.signal.aborted) {
        if (batch?.status === 'active') await cancelUploadBatch(batch.id)
        return
      }
      if (!batch || batch.status !== 'active') {
        batch = await createUploadBatch(
          eligible.map((item) => ({
            client_id: item.clientId,
            filename: item.file.name,
            content_type: getPhotoContentType(item.file),
            size_bytes: item.file.size,
          })),
          uploadGroupIds,
        )
      }
      if (controller.signal.aborted) {
        await cancelUploadBatch(batch.id)
        return
      }
      setActiveBatchId(batch.id)
      setUploadGroupIds(batch.group_ids)
      const serverItems = batch.items.filter((item) => eligible.some((local) => local.clientId === item.client_id))
      let cursor = 0
      let succeeded = 0
      let duplicates = 0
      let failed = 0
      const updateItem = (clientId: string, values: Partial<QueuedUpload>) =>
        setUploadQueue((current) => current.map((item) => (item.clientId === clientId ? { ...item, ...values } : item)))
      const worker = async () => {
        while (cursor < serverItems.length) {
          const serverItem = serverItems[cursor++]
          const local = eligible.find((item) => item.clientId === serverItem.client_id)
          if (!local) continue
          updateItem(local.clientId, { status: 'uploading', errorCode: null })
          try {
            await uploadItemContent(serverItem, local.file, controller.signal, (uploadedBytes) =>
              updateItem(local.clientId, { uploadedBytes }),
            )
            updateItem(local.clientId, { status: 'processing' })
            const completed = await completeUploadItem(serverItem.id)
            updateItem(local.clientId, {
              status:
                completed.status === 'duplicate'
                  ? 'duplicate'
                  : completed.status === 'succeeded'
                    ? 'succeeded'
                    : 'failed',
              errorCode: completed.error_code,
              uploadedBytes: completed.received_bytes,
              photoId: completed.photo_id,
            })
            if (completed.status === 'succeeded') succeeded += 1
            else if (completed.status === 'duplicate') duplicates += 1
            else failed += 1
          } catch (error) {
            if (isUnauthorizedError(error)) throw error
            if (isAbortError(error)) return
            updateItem(local.clientId, { status: 'failed', errorCode: 'network_error' })
            failed += 1
          }
        }
      }
      await Promise.all([worker(), worker()])
      if (controller.signal.aborted) {
        await cancelUploadBatch(batch.id)
        return
      }
      const finalBatch = await getUploadBatch(batch.id)
      if (controller.signal.aborted) {
        if (finalBatch.status === 'active') await cancelUploadBatch(batch.id)
        return
      }
      if (finalBatch.status !== 'active') setActiveBatchId(null)
      await onUploaded()
      if (controller.signal.aborted) return
      setUploadMessage({
        type: failed > 0 ? 'error' : 'success',
        text: i18n.t('photos.uploadResult', {
          saved: succeeded,
          duplicates: duplicates > 0 ? i18n.t('photos.uploadDuplicates', { count: duplicates }) : '',
          failed: failed > 0 ? i18n.t('photos.uploadFailures', { count: failed }) : '',
        }),
      })
    } catch (error) {
      controller.abort()
      if (isAbortError(error)) return
      if (isUnauthorizedError(error)) onUnauthorized()
      else setUploadMessage({ type: 'error', text: getUploadErrorMessage(error) })
    } finally {
      if (uploadControllerRef.current === controller) {
        uploadControllerRef.current = null
        setUploading(false)
      }
    }
  }

  const selectFiles = (files: File[]) => {
    const selected = files.slice(0, MAX_FILES_PER_BATCH)
    if (activeBatchId) {
      abandonedBatchRef.current = cancelUploadBatch(activeBatchId).catch((error: unknown) => {
        if (isUnauthorizedError(error)) onUnauthorized()
      })
    }
    setUploadQueue(
      selected.map((file) => ({
        clientId: createClientId(),
        file,
        status: 'queued',
        uploadedBytes: 0,
        errorCode: null,
        photoId: null,
      })),
    )
    setActiveBatchId(null)
    setUploadMessage(
      files.length > MAX_FILES_PER_BATCH
        ? { type: 'error', text: i18n.t('photos.maxFiles', { count: MAX_FILES_PER_BATCH }) }
        : null,
    )
  }

  const cancelUpload = async () => {
    uploadControllerRef.current?.abort()
    if (activeBatchId) {
      try {
        await cancelUploadBatch(activeBatchId)
      } catch (error) {
        if (isUnauthorizedError(error)) onUnauthorized()
      }
    }
    setActiveBatchId(null)
    setUploadQueue((current) =>
      current.map((item) =>
        ['succeeded', 'duplicate', 'failed'].includes(item.status)
          ? item
          : { ...item, status: 'failed', errorCode: 'canceled' },
      ),
    )
    setUploadMessage({ type: 'error', text: i18n.t('photos.uploadCanceled') })
    setUploading(false)
  }

  const reset = useCallback(() => {
    uploadControllerRef.current?.abort()
    uploadControllerRef.current = null
    abandonedBatchRef.current = null
    setUploadQueue([])
    setUploadGroupIds([])
    setActiveBatchId(null)
    setUploading(false)
    setUploadMessage(null)
  }, [])

  return {
    fileInputRef,
    uploadQueue,
    uploadGroupIds,
    uploadVisibilityLocked: activeBatchId !== null,
    uploading,
    uploadMessage,
    upload,
    selectFiles,
    cancelUpload,
    changeUploadGroups: (groupIds: string[]) => {
      if (!activeBatchId) setUploadGroupIds(groupIds)
    },
    reset,
  }
}
