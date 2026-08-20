import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PublicAuthLayout } from './PublicAuthLayout'

describe('PublicAuthLayout', () => {
  it('renders the shared controls and content slots', async () => {
    const user = userEvent.setup()
    const onToggleTheme = vi.fn()

    render(
      <PublicAuthLayout
        theme="light"
        onToggleTheme={onToggleTheme}
        icon={<span data-testid="brand-icon" />}
        eyebrow={<span lang="en">FAMILY HUB</span>}
        title="ログイン"
        titleId="login-title"
        description="家族のためのアプリ"
      >
        <form aria-label="ログインフォーム">
          <button type="submit">送信</button>
        </form>
      </PublicAuthLayout>,
    )

    expect(screen.getByRole('heading', { name: 'ログイン' })).toBeInTheDocument()
    expect(screen.getByTestId('brand-icon')).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'ログインフォーム' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'ログイン' })).toContainElement(
      screen.getByRole('button', { name: '表示言語をENに切り替える' }),
    )

    await user.click(screen.getByRole('button', { name: 'ダークモードへ切り替える' }))
    expect(onToggleTheme).toHaveBeenCalledOnce()
  })
})
