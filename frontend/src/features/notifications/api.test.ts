import { beforeEach, describe, expect, it, vi } from 'vitest'
import { rememberCsrfToken } from '../../shared/api/client'
import {
  createPushSubscription,
  deletePushSubscription,
  getNotificationConfig,
  updateNotificationLocale,
  updateNotificationPreferences,
} from './api'

describe('notification API', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    rememberCsrfToken('csrf-token')
  })

  it('loads notification configuration without caching', async () => {
    const response = { enabled: false, vapid_public_key: null, subscription_ids: [], preferences: [] }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(response), { headers: { 'Content-Type': 'application/json' } }),
    )

    await expect(getNotificationConfig()).resolves.toEqual(response)
    const request = vi.mocked(fetch).mock.calls[0][0] as Request
    expect(new URL(request.url).pathname).toBe('/api/v1/notifications/config')
    expect(request.credentials).toBe('same-origin')
  })

  it('uses CSRF protection for subscription and preference mutations', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 'subscription-id', locale: 'ja' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { headers: { 'Content-Type': 'application/json' } }))
    const subscription = {
      endpoint: 'https://web.push.apple.com/example',
      keys: { p256dh: 'public-key', auth: 'auth-key' },
      locale: 'ja' as const,
    }
    const preferences = [
      { notification_type: 'photo_shared' as const, enabled: true },
      { notification_type: 'chore_due' as const, enabled: true },
      { notification_type: 'shopping_added' as const, enabled: false },
    ] as const

    await createPushSubscription(subscription)
    await deletePushSubscription('subscription/id')
    await updateNotificationPreferences([...preferences])

    const requests = vi.mocked(fetch).mock.calls.map(([request]) => request as Request)
    expect(requests.map((request) => [new URL(request.url).pathname, request.method])).toEqual([
      ['/api/v1/notifications/subscriptions', 'POST'],
      ['/api/v1/notifications/subscriptions/subscription%2Fid', 'DELETE'],
      ['/api/v1/notifications/preferences', 'PUT'],
    ])
    requests.forEach((request) => expect(request.headers.get('X-CSRF-Token')).toBe('csrf-token'))
    await expect(requests[2].clone().json()).resolves.toEqual({ items: preferences })
  })

  it('updates the current session notification language', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }))

    await updateNotificationLocale('ja')

    const request = vi.mocked(fetch).mock.calls[0][0] as Request
    expect(new URL(request.url).pathname).toBe('/api/v1/notifications/subscriptions/locale')
    expect(request.method).toBe('PUT')
    expect(request.headers.get('X-CSRF-Token')).toBe('csrf-token')
    await expect(request.clone().json()).resolves.toEqual({ locale: 'ja' })
  })
})
