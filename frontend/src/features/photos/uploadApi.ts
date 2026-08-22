import { ApiError, csrfHeaders } from '../../shared/api/client'
import { isAbortError } from '../../shared/api/errors'
import { createClientId } from '../../shared/lib/uuid'
import type { UploadBatchCreate, UploadBatchResponse, UploadItemResponse } from '../../shared/api/generated'
import {
  cancelUploadBatchApiV1UploadBatchesBatchIdDelete,
  completeUploadItemApiV1UploadBatchesItemsItemIdCompletePost,
  createUploadBatchApiV1UploadBatchesPost,
  getUploadBatchApiV1UploadBatchesBatchIdGet,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'
import { getUploadRequestTimeoutMs } from './uploadConfig'

export type UploadBatch = UploadBatchResponse
export type UploadItem = UploadItemResponse

export function createUploadBatch(
  files: Array<{
    client_id: string
    original_filename: string
    declared_content_type: string
    size_bytes: number
  }>,
  groupIds: string[],
): Promise<UploadBatch> {
  const body: UploadBatchCreate = {
    files,
    sharing: { visibility: groupIds.length > 0 ? 'shared' : 'private', group_ids: groupIds },
  }
  return sdkData(createUploadBatchApiV1UploadBatchesPost({ body }))
}

export function getUploadBatch(batchId: string): Promise<UploadBatch> {
  return sdkData(getUploadBatchApiV1UploadBatchesBatchIdGet({ path: { batch_id: batchId } }))
}

export function completeUploadItem(itemId: string): Promise<UploadItem> {
  return sdkData(completeUploadItemApiV1UploadBatchesItemsItemIdCompletePost({ path: { item_id: itemId } }))
}

export function cancelUploadBatch(batchId: string): Promise<void> {
  return sdkData(cancelUploadBatchApiV1UploadBatchesBatchIdDelete({ path: { batch_id: batchId } }))
}

const NETWORK_CHUNK_BYTES = 8 * 1024 * 1024
const UPLOAD_REQUEST_TIMEOUT_MS = getUploadRequestTimeoutMs(import.meta.env)
const MAX_UPLOAD_RETRIES = 3
const UPLOAD_RETRY_DELAY_MS = 250

class UploadRequestTimeoutError extends Error {
  constructor() {
    super('Upload request timed out')
    this.name = 'UploadRequestTimeoutError'
  }
}

class UploadOffsetConflictError extends ApiError {
  readonly actualOffset: number

  constructor(actualOffset: number) {
    super(409, 'Upload offset mismatch')
    this.name = 'UploadOffsetConflictError'
    this.actualOffset = actualOffset
  }
}

function readUploadOffsetValue(value: string | null, status: number): number {
  if (value === null || !/^\d+$/.test(value)) {
    throw new ApiError(status, 'Upload response did not include a valid offset')
  }
  return Number(value)
}

function getUploadContentUrl(itemId: string): string {
  const apiOrigin = import.meta.env.DEV
    ? `${window.location.protocol}//${window.location.hostname}:18000`
    : window.location.origin
  return `${apiOrigin}/api/v1/upload-batches/items/${encodeURIComponent(itemId)}/content`
}

interface UploadResponse {
  status: number
  uploadOffset: string | null
  requestId: string | null
}

type UploadRoute = 'direct' | 'same-origin'

interface UploadRequestDiagnostic {
  attemptId: string
  itemId: string
  method: 'HEAD' | 'PATCH'
  offset: number | null
  bytes: number
  retryCount: number
  route: UploadRoute
}

function getUploadRoute(): UploadRoute {
  return import.meta.env.DEV ? 'direct' : 'same-origin'
}

function getUploadErrorDetails(error: unknown): { errorName: string; status?: number } {
  if (error instanceof ApiError) return { errorName: error.name, status: error.status }
  if (error instanceof Error) return { errorName: error.name }
  return { errorName: typeof error }
}

function logUploadRequest(
  level: 'info' | 'warn',
  event: string,
  diagnostic: UploadRequestDiagnostic,
  details: Record<string, unknown> = {},
): void {
  console[level](`[photo-upload] ${event}`, {
    timestamp: new Date().toISOString(),
    ...diagnostic,
    ...details,
  })
}

async function sendUploadRequest(
  itemId: string,
  method: 'HEAD' | 'PATCH',
  signal: AbortSignal,
  diagnostic: UploadRequestDiagnostic,
  body: Blob | null = null,
  headers: Record<string, string> = {},
): Promise<UploadResponse> {
  if (signal.aborted) throw new DOMException('The upload was canceled', 'AbortError')
  const started = performance.now()
  logUploadRequest('info', 'request-started', diagnostic)
  const timeoutController = new AbortController()
  let timedOut = false
  const abortRequest = () => timeoutController.abort()
  const timeoutId = setTimeout(() => {
    timedOut = true
    timeoutController.abort()
  }, UPLOAD_REQUEST_TIMEOUT_MS)
  signal.addEventListener('abort', abortRequest, { once: true })
  try {
    const response = await fetch(getUploadContentUrl(itemId), {
      method,
      body,
      cache: 'no-store',
      credentials: 'include',
      headers,
      signal: timeoutController.signal,
    })
    const uploadResponse = {
      status: response.status,
      uploadOffset: response.headers.get('Upload-Offset'),
      requestId: response.headers.get('X-Request-ID'),
    }
    if (method === 'PATCH' && diagnostic.route === 'direct') timeoutController.abort()
    return uploadResponse
  } catch (error) {
    const resolvedError = signal.aborted
      ? new DOMException('The upload was canceled', 'AbortError')
      : timedOut
        ? new UploadRequestTimeoutError()
        : error
    logUploadRequest('warn', 'request-failed', diagnostic, {
      durationMs: Math.round(performance.now() - started),
      timedOut,
      ...getUploadErrorDetails(resolvedError),
    })
    throw resolvedError
  } finally {
    clearTimeout(timeoutId)
    signal.removeEventListener('abort', abortRequest)
  }
}

async function getUploadOffset(itemId: string, signal: AbortSignal): Promise<number> {
  const diagnostic: UploadRequestDiagnostic = {
    attemptId: createClientId(),
    itemId,
    method: 'HEAD',
    offset: null,
    bytes: 0,
    retryCount: 0,
    route: getUploadRoute(),
  }
  const started = performance.now()
  const response = await sendUploadRequest(itemId, 'HEAD', signal, diagnostic)
  logUploadRequest('info', 'request-completed', diagnostic, {
    durationMs: Math.round(performance.now() - started),
    status: response.status,
    uploadOffset: response.uploadOffset,
    requestId: response.requestId,
  })
  if (response.status < 200 || response.status >= 300) {
    throw new ApiError(response.status, 'Could not read upload offset')
  }
  return readUploadOffsetValue(response.uploadOffset, response.status)
}

async function sendUploadChunk(
  itemId: string,
  offset: number,
  chunk: Blob,
  retryCount: number,
  signal: AbortSignal,
): Promise<number> {
  const diagnostic: UploadRequestDiagnostic = {
    attemptId: createClientId(),
    itemId,
    method: 'PATCH',
    offset,
    bytes: chunk.size,
    retryCount,
    route: getUploadRoute(),
  }
  const started = performance.now()
  const response = await sendUploadRequest(itemId, 'PATCH', signal, diagnostic, chunk, {
    ...csrfHeaders(),
    'Content-Type': 'application/offset+octet-stream',
    'X-Upload-Attempt-ID': diagnostic.attemptId,
    'X-Upload-Retry-Count': String(retryCount),
    'X-Upload-Route': diagnostic.route,
    'Upload-Offset': String(offset),
  })
  logUploadRequest('info', 'request-completed', diagnostic, {
    durationMs: Math.round(performance.now() - started),
    status: response.status,
    uploadOffset: response.uploadOffset,
    requestId: response.requestId,
  })
  const nextOffset = readUploadOffsetValue(response.uploadOffset, response.status)
  if (response.status === 409) throw new UploadOffsetConflictError(nextOffset)
  if (response.status !== 200) {
    throw new ApiError(response.status, `Upload failed with status ${response.status}`)
  }
  return nextOffset
}

function isRetryableUploadError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return error.status === 408 || error.status === 409 || error.status === 429 || error.status >= 500
}

async function waitBeforeUploadRetry(signal: AbortSignal): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('The upload was canceled', 'AbortError'))
      return
    }
    function abort() {
      clearTimeout(timeoutId)
      signal.removeEventListener('abort', abort)
      reject(new DOMException('The upload was canceled', 'AbortError'))
    }
    const timeoutId = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, UPLOAD_RETRY_DELAY_MS)
    signal.addEventListener('abort', abort, { once: true })
  })
}

export async function uploadItemContent(
  item: UploadItem,
  file: File,
  signal: AbortSignal,
  onProgress: (uploadedBytes: number) => void,
): Promise<void> {
  let offset = await getUploadOffset(item.id, signal)
  if (offset > file.size) throw new ApiError(409, 'Stored upload exceeds the selected file')
  onProgress(offset)
  while (offset < file.size) {
    let retryCount = 0
    while (offset < file.size) {
      const chunk = file.slice(offset, Math.min(offset + NETWORK_CHUNK_BYTES, file.size))
      if (chunk.size === 0) throw new ApiError(409, 'Selected file could not be read')
      try {
        const nextOffset = await sendUploadChunk(item.id, offset, chunk, retryCount, signal)
        if (nextOffset <= offset || nextOffset > file.size) {
          throw new ApiError(409, 'Upload did not advance to a valid offset')
        }
        offset = nextOffset
        onProgress(offset)
        break
      } catch (error) {
        if (isAbortError(error) || !isRetryableUploadError(error) || retryCount >= MAX_UPLOAD_RETRIES) {
          console.warn('[photo-upload] chunk-failed', {
            timestamp: new Date().toISOString(),
            itemId: item.id,
            offset,
            bytes: chunk.size,
            retryCount,
            ...getUploadErrorDetails(error),
          })
          throw error
        }
        retryCount += 1
        if (error instanceof UploadOffsetConflictError) {
          const previousOffset = offset
          if (error.actualOffset > file.size) throw new ApiError(409, 'Stored upload exceeds the selected file')
          if (error.actualOffset !== offset) {
            offset = error.actualOffset
            onProgress(offset)
          }
          if (offset > previousOffset) break
        }
        console.warn('[photo-upload] chunk-retry-scheduled', {
          timestamp: new Date().toISOString(),
          itemId: item.id,
          offset,
          bytes: chunk.size,
          retryCount,
          ...getUploadErrorDetails(error),
        })
        await waitBeforeUploadRetry(signal)
      }
    }
  }
}
