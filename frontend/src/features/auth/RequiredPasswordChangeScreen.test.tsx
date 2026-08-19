import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { RequiredPasswordChangeScreen } from './RequiredPasswordChangeScreen'

const { changePassword, logout } = vi.hoisted(() => ({
  changePassword: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('./api', () => ({ changePassword, logout }))

describe('RequiredPasswordChangeScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    changePassword.mockResolvedValue(undefined)
    logout.mockResolvedValue(undefined)
  })

  it('changes the temporary password and ends the current session', async () => {
    const user = userEvent.setup()
    const onSessionEnded = vi.fn()
    render(
      <RequiredPasswordChangeScreen
        username="family-member"
        theme="light"
        onSessionEnded={onSessionEnded}
        onToggleTheme={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('仮パスワード'), 'temporary-password')
    await user.type(screen.getByLabelText('新しいパスワード'), 'new-password')
    await user.type(screen.getByLabelText('新しいパスワード（確認）'), 'new-password')
    await user.click(screen.getByRole('button', { name: 'パスワードを変更' }))

    expect(changePassword).toHaveBeenCalledWith('temporary-password', 'new-password')
    expect(onSessionEnded).toHaveBeenCalledOnce()
  })

  it('rejects mismatched passwords before making a request', async () => {
    const user = userEvent.setup()
    render(
      <RequiredPasswordChangeScreen
        username="family-member"
        theme="light"
        onSessionEnded={vi.fn()}
        onToggleTheme={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('仮パスワード'), 'temporary-password')
    await user.type(screen.getByLabelText('新しいパスワード'), 'new-password')
    await user.type(screen.getByLabelText('新しいパスワード（確認）'), 'different-password')
    await user.click(screen.getByRole('button', { name: 'パスワードを変更' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('新しいパスワードが一致しません。')
    expect(changePassword).not.toHaveBeenCalled()
  })

  it('reports an incorrect temporary password', async () => {
    const user = userEvent.setup()
    changePassword.mockRejectedValue(new ApiError(400, 'incorrect'))
    render(
      <RequiredPasswordChangeScreen
        username="family-member"
        theme="light"
        onSessionEnded={vi.fn()}
        onToggleTheme={vi.fn()}
      />,
    )

    await user.type(screen.getByLabelText('仮パスワード'), 'wrong-password')
    await user.type(screen.getByLabelText('新しいパスワード'), 'new-password')
    await user.type(screen.getByLabelText('新しいパスワード（確認）'), 'new-password')
    await user.click(screen.getByRole('button', { name: 'パスワードを変更' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('仮パスワードが正しくありません。')
  })
})
