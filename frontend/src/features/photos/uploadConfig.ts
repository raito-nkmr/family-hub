const DEVELOPMENT_UPLOAD_REQUEST_TIMEOUT_MS = 5_000
const PRODUCTION_UPLOAD_REQUEST_TIMEOUT_MS = 30_000
const MIN_UPLOAD_REQUEST_TIMEOUT_MS = 1_000
const MAX_UPLOAD_REQUEST_TIMEOUT_MS = 300_000

interface UploadTimeoutEnvironment {
  DEV: boolean
  VITE_UPLOAD_REQUEST_TIMEOUT_MS?: string
}

export function getUploadRequestTimeoutMs(environment: UploadTimeoutEnvironment): number {
  const configured = Number(environment.VITE_UPLOAD_REQUEST_TIMEOUT_MS)
  if (
    Number.isInteger(configured) &&
    configured >= MIN_UPLOAD_REQUEST_TIMEOUT_MS &&
    configured <= MAX_UPLOAD_REQUEST_TIMEOUT_MS
  ) {
    return configured
  }

  return environment.DEV ? DEVELOPMENT_UPLOAD_REQUEST_TIMEOUT_MS : PRODUCTION_UPLOAD_REQUEST_TIMEOUT_MS
}
