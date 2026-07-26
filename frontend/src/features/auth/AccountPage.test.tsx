import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AccountPage } from './AccountPage'
import { changePassword, getSessions, logoutAll, revokeSession } from './api'
import { createAppWrapper } from '../../test/renderWithAppProviders'

vi.mock('./api', () => ({
  changePassword: vi.fn(),
  getSessions: vi.fn(),
  logoutAll: vi.fn(),
  revokeSession: vi.fn(),
}))

vi.mock('../notifications/NotificationSettings', () => ({
  NotificationSettings: () => <section aria-label="通知設定" />,
}))

const currentSession = {
  id: 'current-session',
  created_at: '2026-07-16T01:00:00Z',
  last_seen_at: '2026-07-16T02:00:00Z',
  expires_at: '2026-08-16T01:00:00Z',
  current: true,
}

const otherSession = {
  ...currentSession,
  id: 'other-session',
  current: false,
}

describe('AccountPage', () => {
  beforeEach(() => {
    vi.mocked(getSessions).mockResolvedValue({ items: [currentSession, otherSession] })
    vi.mocked(changePassword).mockResolvedValue(undefined)
    vi.mocked(revokeSession).mockResolvedValue(undefined)
    vi.mocked(logoutAll).mockResolvedValue(undefined)
  })

  it('lists sessions and revokes another session', async () => {
    const user = userEvent.setup()
    render(
      <AccountPage
        username="owner"
        onSessionEnded={vi.fn()}
        showPwaInstallGuideEntry={false}
        onShowPwaInstallGuide={vi.fn()}
      />,
      { wrapper: createAppWrapper() },
    )

    expect(await screen.findByText('現在のセッション')).toBeInTheDocument()
    expect(screen.getByText('ほかのセッション')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '失効する' }))

    expect(revokeSession).toHaveBeenCalledWith('other-session', expect.anything())
    expect(screen.queryByText('ほかのセッション')).not.toBeInTheDocument()
  })

  it('checks password confirmation before submitting', async () => {
    const user = userEvent.setup()
    render(
      <AccountPage
        username="owner"
        onSessionEnded={vi.fn()}
        showPwaInstallGuideEntry={false}
        onShowPwaInstallGuide={vi.fn()}
      />,
      { wrapper: createAppWrapper() },
    )
    await screen.findByText('現在のセッション')

    await user.type(screen.getByLabelText('現在のパスワード'), 'current-password')
    await user.type(screen.getByLabelText('新しいパスワード'), 'new-password')
    await user.type(screen.getByLabelText('新しいパスワード（確認）'), 'different-password')
    await user.click(screen.getByRole('button', { name: 'パスワードを変更' }))

    expect(screen.getByText('新しいパスワードが一致しません。')).toBeInTheDocument()
    expect(changePassword).not.toHaveBeenCalled()
  })

  it('ends the local session after changing the password', async () => {
    const user = userEvent.setup()
    const onSessionEnded = vi.fn()
    render(
      <AccountPage
        username="owner"
        onSessionEnded={onSessionEnded}
        showPwaInstallGuideEntry={false}
        onShowPwaInstallGuide={vi.fn()}
      />,
      { wrapper: createAppWrapper() },
    )
    await screen.findByText('現在のセッション')

    await user.type(screen.getByLabelText('現在のパスワード'), 'current-password')
    await user.type(screen.getByLabelText('新しいパスワード'), 'new-password')
    await user.type(screen.getByLabelText('新しいパスワード（確認）'), 'new-password')
    await user.click(screen.getByRole('button', { name: 'パスワードを変更' }))

    expect(changePassword).toHaveBeenCalledWith('current-password', 'new-password')
    expect(onSessionEnded).toHaveBeenCalled()
  })

  it('keeps the Home Screen guide available from the account page', async () => {
    const user = userEvent.setup()
    const onShowPwaInstallGuide = vi.fn()
    render(
      <AccountPage
        username="owner"
        onSessionEnded={vi.fn()}
        showPwaInstallGuideEntry={true}
        onShowPwaInstallGuide={onShowPwaInstallGuide}
      />,
      { wrapper: createAppWrapper() },
    )

    await user.click(screen.getByRole('button', { name: '追加方法を見る' }))

    expect(onShowPwaInstallGuide).toHaveBeenCalledOnce()
  })
})
