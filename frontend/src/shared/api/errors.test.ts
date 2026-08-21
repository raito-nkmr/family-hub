import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { isAbortError, isApiErrorWithCode, isApiErrorWithStatus, isUnauthorizedError, readApiErrorCode } from './errors'

describe('API error predicates', () => {
  it('matches API errors by status', () => {
    const error = new ApiError(409, 'conflict')

    expect(isApiErrorWithStatus(error, 409)).toBe(true)
    expect(isApiErrorWithStatus(error, 401)).toBe(false)
    expect(isApiErrorWithCode(new ApiError(409, 'conflict', 'endpoint_conflict'), 'endpoint_conflict')).toBe(true)
    expect(isApiErrorWithCode(error, 'other')).toBe(false)
    expect(isUnauthorizedError(new ApiError(401, 'expired'))).toBe(true)
    expect(isUnauthorizedError(new Error('network'))).toBe(false)
  })

  it('reads machine-readable codes from generated API error details', () => {
    expect(readApiErrorCode({ detail: { code: 'example' } })).toBe('example')
    expect(readApiErrorCode({ detail: 'forbidden' })).toBeUndefined()
  })

  it('recognizes aborted browser requests', () => {
    expect(isAbortError(new DOMException('aborted', 'AbortError'))).toBe(true)
    expect(isAbortError(new Error('aborted'))).toBe(false)
  })
})
