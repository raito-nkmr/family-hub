import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearCsrfToken, csrfHeaders, rememberCsrfToken } from './client'

afterEach(() => {
  clearCsrfToken()
  vi.unstubAllGlobals()
})

describe('CSRF token storage', () => {
  it('exposes the token only as a request header', () => {
    rememberCsrfToken('csrf-token')

    expect(csrfHeaders()).toEqual({ 'X-CSRF-Token': 'csrf-token' })
  })
})
