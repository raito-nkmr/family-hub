import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearCsrfToken, csrfHeaders, rememberCsrfToken, request } from './client'

afterEach(() => {
  clearCsrfToken()
  vi.unstubAllGlobals()
})

describe('request', () => {
  it('sends same-origin credentials and returns JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(request<{ status: string }>('/api/v1/health')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/health', {
      credentials: 'same-origin',
      headers: expect.any(Headers),
    })
  })

  it('returns undefined for an empty successful response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))

    await expect(request<void>('/api/v1/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })

  it('clears the CSRF token when authentication expires', async () => {
    rememberCsrfToken('csrf-token')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })))

    await expect(request('/api/v1/photos')).rejects.toMatchObject({ status: 401 })
    expect(csrfHeaders()).toEqual({})
  })
})

describe('CSRF token storage', () => {
  it('exposes the token only as a request header', () => {
    rememberCsrfToken('csrf-token')

    expect(csrfHeaders()).toEqual({ 'X-CSRF-Token': 'csrf-token' })
  })
})
