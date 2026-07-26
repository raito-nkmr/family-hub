import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../../shared/api/client'
import { LoginScreen } from './LoginScreen'

describe('LoginScreen', () => {
  it('submits the entered credentials', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn().mockResolvedValue(undefined)
    render(<LoginScreen initialError={null} theme="light" onLogin={onLogin} onToggleTheme={vi.fn()} />)

    expect(screen.getByText('FAMILY HUB')).toHaveAttribute('lang', 'en')
    await user.type(screen.getByLabelText('ユーザー名'), 'owner')
    await user.type(screen.getByLabelText('パスワード'), 'correct horse battery staple')
    await user.click(screen.getByRole('button', { name: 'ログイン' }))

    expect(onLogin).toHaveBeenCalledWith('owner', 'correct horse battery staple')
  })

  it('shows a safe error for invalid credentials', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn().mockRejectedValue(new ApiError(401, 'unauthorized'))
    render(<LoginScreen initialError={null} theme="light" onLogin={onLogin} onToggleTheme={vi.fn()} />)

    await user.type(screen.getByLabelText('ユーザー名'), 'owner')
    await user.type(screen.getByLabelText('パスワード'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'ログイン' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('ユーザー名またはパスワードが正しくありません。')
  })
})
