import { ApiError } from './client'

export function isApiErrorWithStatus(error: unknown, status: number): error is ApiError {
  return error instanceof ApiError && error.status === status
}

export function isUnauthorizedError(error: unknown): error is ApiError {
  return isApiErrorWithStatus(error, 401)
}

export function isAbortError(error: unknown): error is DOMException {
  return error instanceof DOMException && error.name === 'AbortError'
}
