import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { getCurrentSession } from './features/auth/api'
import App from './App'

vi.mock('./features/auth/api', () => ({
  getCurrentSession: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('./app/AuthenticatedApp', () => ({
  AuthenticatedApp: ({ currentUser }: { currentUser: { username: string } }) => (
    <main>Authenticated as {currentUser.username}</main>
  ),
}))

function renderApp(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App routes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the privacy page without checking a login session', () => {
    renderApp('/privacy')

    expect(screen.getByRole('heading', { level: 1, name: 'プライバシー' })).toBeInTheDocument()
    expect(getCurrentSession).not.toHaveBeenCalled()
  })

  it('restores a session before rendering a protected deep link', async () => {
    vi.mocked(getCurrentSession).mockResolvedValue({
      id: 'user-id',
      username: 'family-member',
      system_role: 'user',
      must_change_password: false,
    })

    renderApp('/photos/library')

    expect(screen.getByLabelText('認証状態を確認中')).toBeInTheDocument()
    expect(await screen.findByText('Authenticated as family-member')).toBeInTheDocument()
  })

  it('restores a session when leaving a directly opened privacy page', async () => {
    const user = userEvent.setup()
    vi.mocked(getCurrentSession).mockResolvedValue({
      id: 'user-id',
      username: 'family-member',
      system_role: 'user',
      must_change_password: false,
    })
    renderApp('/privacy')

    expect(getCurrentSession).not.toHaveBeenCalled()
    await user.click(screen.getByRole('link', { name: /Family Hub/ }))

    expect(await screen.findByText('Authenticated as family-member')).toBeInTheDocument()
    expect(getCurrentSession).toHaveBeenCalledOnce()
  })

  it('gives an invitation fragment precedence over session restoration', () => {
    renderApp('/invitations#invite=invitation-token')

    expect(screen.getByRole('heading', { name: 'アカウントを作成' })).toBeInTheDocument()
    expect(getCurrentSession).not.toHaveBeenCalled()
  })
})
