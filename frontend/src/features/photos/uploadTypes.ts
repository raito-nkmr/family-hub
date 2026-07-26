export type LocalUploadStatus = 'queued' | 'uploading' | 'processing' | 'succeeded' | 'duplicate' | 'failed'

export interface QueuedUpload {
  clientId: string
  file: File
  status: LocalUploadStatus
  uploadedBytes: number
  errorCode: string | null
  photoId: string | null
}
