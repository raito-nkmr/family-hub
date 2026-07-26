import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { acceptInvitation } from './api'
import { InvitationAcceptanceScreen } from './InvitationAcceptanceScreen'

vi.mock('./api', () => ({ acceptInvitation: vi.fn() }))

describe('InvitationAcceptanceScreen', () => {
  beforeEach(() => vi.clearAllMocks())

  it('creates an account from the invitation token', async () => {
    const user = userEvent.setup()
    vi.mocked(acceptInvitation).mockResolvedValue({
      id: 'user-1',
      username: 'family-member',
      system_role: 'user',
    })
    render(
      <InvitationAcceptanceScreen
        token="invitation-token"
        theme="light"
        onContinueToLogin={vi.fn()}
        onToggleTheme={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('パスワード'), 'eight888')
    await user.type(screen.getByLabelText('パスワード（確認）'), 'eight888')
    await user.click(screen.getByRole('button', { name: 'アカウントを作成' }))

    expect(acceptInvitation).toHaveBeenCalledWith('invitation-token', 'eight888')
    expect(await screen.findByText(/family-member/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'ログインへ進む' })).toBeInTheDocument()
  })

  it('rejects mismatched password confirmation without calling the API', async () => {
    const user = userEvent.setup()
    render(
      <InvitationAcceptanceScreen
        token="invitation-token"
        theme="light"
        onContinueToLogin={vi.fn()}
        onToggleTheme={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('パスワード'), 'a-secure-family-password')
    await user.type(screen.getByLabelText('パスワード（確認）'), 'a-different-password')
    await user.click(screen.getByRole('button', { name: 'アカウントを作成' }))

    expect(acceptInvitation).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('確認用パスワードが一致しません。')
  })
})
