import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { getCurrentSession, login } from './features/auth/api'
import App from './App'
import { queryClient } from './shared/api/queryClient'

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

function renderAppInStrictMode(initialEntry: string) {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[initialEntry]}>
        <App />
      </MemoryRouter>
    </StrictMode>,
  )
}

describe('App routes', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    queryClient.clear()
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

  it('continues restoring a session after StrictMode aborts the first check', async () => {
    const session = {
      id: 'user-id',
      username: 'family-member',
      system_role: 'user' as const,
      must_change_password: false,
    }
    vi.mocked(getCurrentSession).mockImplementation(
      (signal) =>
        new Promise((resolve, reject) => {
          const timeoutId = window.setTimeout(() => resolve(session), 25)
          signal?.addEventListener(
            'abort',
            () => {
              window.clearTimeout(timeoutId)
              reject(new DOMException('Aborted', 'AbortError'))
            },
            { once: true },
          )
        }),
    )

    renderAppInStrictMode('/photos/library')

    expect(await screen.findByText('Authenticated as family-member')).toBeInTheDocument()
    expect(getCurrentSession).toHaveBeenCalledTimes(2)
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

  it('restores an existing session after leaving an invitation fragment', async () => {
    const user = userEvent.setup()
    vi.mocked(getCurrentSession).mockResolvedValue({
      id: 'user-id',
      username: 'family-member',
      system_role: 'user',
      must_change_password: false,
    })

    renderApp('/invitations#invite=invitation-token')
    await user.click(screen.getByRole('button', { name: '招待を使わずログインへ戻る' }))

    expect(await screen.findByText('Authenticated as family-member')).toBeInTheDocument()
    expect(getCurrentSession).toHaveBeenCalledOnce()
  })

  it('clears previous user data before showing a newly logged-in account', async () => {
    const user = userEvent.setup()
    vi.mocked(login).mockResolvedValue({
      id: 'new-user-id',
      username: 'new-user',
      system_role: 'user',
      must_change_password: false,
    })
    queryClient.setQueryData(['groups'], [{ id: 'previous-user-group' }])

    renderApp('/')
    await user.type(await screen.findByLabelText('ユーザー名'), 'new-user')
    await user.type(await screen.findByLabelText('パスワード'), 'password')
    await user.click(screen.getByRole('button', { name: 'ログイン' }))

    expect(await screen.findByText('Authenticated as new-user')).toBeInTheDocument()
    expect(queryClient.getQueryData(['groups'])).toBeUndefined()
  })
})
