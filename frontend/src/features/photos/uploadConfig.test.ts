import { describe, expect, it } from 'vitest'
import { getUploadRequestTimeoutMs } from './uploadConfig'

describe('getUploadRequestTimeoutMs', () => {
  it('uses the configured timeout when it is within the safe range', () => {
    expect(getUploadRequestTimeoutMs({ DEV: false, VITE_UPLOAD_REQUEST_TIMEOUT_MS: '45000' })).toBe(45_000)
  })

  it('keeps the short diagnostic timeout for development by default', () => {
    expect(getUploadRequestTimeoutMs({ DEV: true })).toBe(5_000)
  })

  it('uses the production fallback when no measured value is supplied', () => {
    expect(getUploadRequestTimeoutMs({ DEV: false })).toBe(30_000)
  })

  it('ignores invalid or unsafe values', () => {
    expect(getUploadRequestTimeoutMs({ DEV: false, VITE_UPLOAD_REQUEST_TIMEOUT_MS: '0' })).toBe(30_000)
    expect(getUploadRequestTimeoutMs({ DEV: false, VITE_UPLOAD_REQUEST_TIMEOUT_MS: '301000' })).toBe(30_000)
    expect(getUploadRequestTimeoutMs({ DEV: false, VITE_UPLOAD_REQUEST_TIMEOUT_MS: 'not-a-number' })).toBe(30_000)
  })
})
