import { ApiError } from './client'

export function isApiErrorWithStatus(error: unknown, status: number): error is ApiError {
  return error instanceof ApiError && error.status === status
}

export function isApiErrorWithCode(error: unknown, code: string): boolean {
  return error instanceof ApiError && error.code === code
}

export function isUnauthorizedError(error: unknown): error is ApiError {
  return isApiErrorWithStatus(error, 401)
}

export function isAbortError(error: unknown): error is DOMException {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function readApiErrorCode(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null || !('detail' in error)) return undefined
  const detail = error.detail
  if (typeof detail !== 'object' || detail === null || !('code' in detail)) return undefined
  return typeof detail.code === 'string' ? detail.code : undefined
}
