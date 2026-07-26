import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { NotificationSettings } from './NotificationSettings'
import { useNotificationSettings } from './useNotificationSettings'

vi.mock('./useNotificationSettings', () => ({ useNotificationSettings: vi.fn() }))

describe('NotificationSettings', () => {
  it('shows active notification types and saves changed preferences', async () => {
    const user = userEvent.setup()
    const setPreference = vi.fn()
    const savePreferences = vi.fn()
    vi.mocked(useNotificationSettings).mockReturnValue({
      config: {
        enabled: true,
        vapid_public_key: 'AQID',
        subscription_ids: ['subscription-id'],
        preferences: [],
      },
      preferences: [
        { notification_type: 'photo_shared', enabled: true },
        { notification_type: 'cleaning_due', enabled: true },
        { notification_type: 'shopping_added', enabled: false },
      ],
      permission: 'granted',
      loading: false,
      busyAction: null,
      error: null,
      subscribed: true,
      enable: vi.fn(),
      disable: vi.fn(),
      setPreference,
      savePreferences,
    })

    render(<NotificationSettings showInstallGuide={false} onShowInstallGuide={vi.fn()} onUnauthorized={vi.fn()} />)

    expect(screen.getByText('この端末で通知が有効です。')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /買い物の追加/ }))
    await user.click(screen.getByRole('button', { name: '通知設定を保存' }))

    expect(setPreference).toHaveBeenCalledWith('shopping_added', true)
    expect(savePreferences).toHaveBeenCalledOnce()
  })
})
