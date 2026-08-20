import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { updateNotificationLocale } from './api'
import { useNotificationLocaleSync } from './useNotificationLocaleSync'

vi.mock('./api', () => ({ updateNotificationLocale: vi.fn() }))

describe('useNotificationLocaleSync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(updateNotificationLocale).mockResolvedValue(undefined)
  })

  it('updates existing subscriptions after the UI language changes', async () => {
    const { rerender } = renderHook(
      ({ locale }: { locale: 'en' | 'ja' }) => useNotificationLocaleSync({ locale, onUnauthorized: vi.fn() }),
      {
        initialProps: { locale: 'en' as 'en' | 'ja' },
        wrapper: createAppWrapper(),
      },
    )

    rerender({ locale: 'ja' })

    await waitFor(() => expect(updateNotificationLocale).toHaveBeenCalledWith('ja'))
  })

  it('does not block the language change when the locale update fails', async () => {
    vi.mocked(updateNotificationLocale).mockRejectedValue(new Error('offline'))
    const onUnauthorized = vi.fn()
    const { rerender } = renderHook(
      ({ locale }: { locale: 'en' | 'ja' }) => useNotificationLocaleSync({ locale, onUnauthorized }),
      {
        initialProps: { locale: 'en' as 'en' | 'ja' },
        wrapper: createAppWrapper(),
      },
    )

    rerender({ locale: 'ja' })

    await waitFor(() => expect(updateNotificationLocale).toHaveBeenCalledWith('ja'))
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('logs out when the locale update returns 401', async () => {
    vi.mocked(updateNotificationLocale).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()
    const { rerender } = renderHook(
      ({ locale }: { locale: 'en' | 'ja' }) => useNotificationLocaleSync({ locale, onUnauthorized }),
      {
        initialProps: { locale: 'en' as 'en' | 'ja' },
        wrapper: createAppWrapper(),
      },
    )

    rerender({ locale: 'ja' })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })
})
