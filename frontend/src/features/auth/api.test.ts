import { afterEach, describe, expect, it, vi } from 'vitest'
import { changePassword, getSessions, logoutAll, revokeSession } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('account security API', () => {
  it('loads and revokes sessions', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await getSessions()
    await revokeSession('session-1')

    const request = fetchMock.mock.calls[1][0] as Request
    expect(new URL(request.url).pathname).toBe('/api/v1/auth/sessions/session-1')
    expect(request.method).toBe('DELETE')
  })

  it('changes the password and can log out all sessions', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await changePassword('current-password', 'new-password')
    await logoutAll()

    const passwordRequest = fetchMock.mock.calls[0][0] as Request
    expect(new URL(passwordRequest.url).pathname).toBe('/api/v1/auth/password')
    expect(passwordRequest.method).toBe('PUT')
    await expect(passwordRequest.clone().json()).resolves.toEqual({
      current_password: 'current-password',
      new_password: 'new-password',
    })
    const logoutRequest = fetchMock.mock.calls[1][0] as Request
    expect(new URL(logoutRequest.url).pathname).toBe('/api/v1/auth/logout-all')
    expect(logoutRequest.method).toBe('POST')
  })
})
