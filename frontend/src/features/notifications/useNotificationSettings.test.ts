import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createPushSubscription,
  deletePushSubscription,
  getNotificationConfig,
  updateNotificationPreferences,
} from './api'
import { useNotificationSettings } from './useNotificationSettings'
import { createAppWrapper } from '../../test/renderWithAppProviders'

vi.mock('./api', () => ({
  createPushSubscription: vi.fn(),
  deletePushSubscription: vi.fn(),
  getNotificationConfig: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}))

const preferences = [
  { notification_type: 'photo_shared' as const, enabled: true },
  { notification_type: 'cleaning_due' as const, enabled: true },
  { notification_type: 'shopping_added' as const, enabled: false },
]

const subscription = {
  toJSON: () => ({
    endpoint: 'https://web.push.apple.com/example',
    keys: { p256dh: 'public-key', auth: 'auth-key' },
  }),
  unsubscribe: vi.fn().mockResolvedValue(true),
} as unknown as PushSubscription

const getSubscription = vi.fn<() => Promise<PushSubscription | null>>()
const subscribe = vi.fn<() => Promise<PushSubscription>>()
const registration = {
  pushManager: { getSubscription, subscribe },
} as unknown as ServiceWorkerRegistration
const getRegistration = vi.fn().mockResolvedValue(registration)

describe('useNotificationSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('Notification', {
      permission: 'default',
      requestPermission: vi.fn().mockResolvedValue('granted'),
    })
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: { getRegistration },
    })
    vi.mocked(getNotificationConfig).mockResolvedValue({
      enabled: true,
      vapid_public_key: 'AQID',
      subscription_ids: [],
      preferences,
    })
    vi.mocked(createPushSubscription).mockResolvedValue({ id: 'server-subscription', locale: 'ja' })
    vi.mocked(deletePushSubscription).mockResolvedValue(undefined)
    vi.mocked(updateNotificationPreferences).mockResolvedValue(preferences)
    getSubscription.mockResolvedValue(null)
    subscribe.mockResolvedValue(subscription)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    Reflect.deleteProperty(navigator, 'serviceWorker')
  })

  it('requests permission from the enable action and registers the browser subscription', async () => {
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useNotificationSettings({ locale: 'ja', onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.enable())

    expect(Notification.requestPermission).toHaveBeenCalledOnce()
    expect(subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: new Uint8Array([1, 2, 3]),
    })
    expect(createPushSubscription).toHaveBeenCalledWith(
      {
        endpoint: 'https://web.push.apple.com/example',
        keys: { p256dh: 'public-key', auth: 'auth-key' },
        locale: 'ja',
      },
      expect.anything(),
    )
    await waitFor(() => expect(result.current.subscribed).toBe(true))
  })

  it('supports registration pushManager without a global PushManager constructor', async () => {
    expect('PushManager' in window).toBe(false)
    const { result } = renderHook(() => useNotificationSettings({ locale: 'ja', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.permission).toBe('default')
    await act(() => result.current.enable())
    expect(subscribe).toHaveBeenCalledOnce()
  })

  it('deletes the server registration and browser subscription when disabled', async () => {
    getSubscription.mockResolvedValue(subscription)
    vi.mocked(getNotificationConfig).mockResolvedValue({
      enabled: true,
      vapid_public_key: 'AQID',
      subscription_ids: ['server-subscription'],
      preferences,
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useNotificationSettings({ locale: 'ja', onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.subscribed).toBe(true))

    await act(() => result.current.disable())

    expect(deletePushSubscription).toHaveBeenCalledWith('server-subscription', expect.anything())
    expect(subscription.unsubscribe).toHaveBeenCalledOnce()
    await waitFor(() => expect(result.current.subscribed).toBe(false))
  })

  it('does not create a subscription when permission is denied', async () => {
    vi.mocked(Notification.requestPermission).mockResolvedValue('denied')
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useNotificationSettings({ locale: 'ja', onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.enable())

    expect(subscribe).not.toHaveBeenCalled()
    expect(createPushSubscription).not.toHaveBeenCalled()
    expect(result.current.error).toBe('permissionDenied')
  })

  it('keeps existing server subscriptions when registration fails', async () => {
    vi.mocked(getNotificationConfig).mockResolvedValue({
      enabled: true,
      vapid_public_key: 'AQID',
      subscription_ids: ['old-server-subscription'],
      preferences,
    })
    vi.mocked(createPushSubscription).mockRejectedValue(new Error('registration failed'))

    const { result } = renderHook(() => useNotificationSettings({ locale: 'ja', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.enable())

    expect(deletePushSubscription).not.toHaveBeenCalled()
    expect(result.current.error).toBe('subscribe')
  })
})
