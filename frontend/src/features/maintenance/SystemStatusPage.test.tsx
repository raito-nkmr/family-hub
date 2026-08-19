import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCurrentSession, type AuthUser } from '../auth/api'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import {
  getAdministrationSnapshot,
  getSystemStatus,
  updateAdministrativeUserRole,
  type AdministrationSnapshot,
  type SystemStatus,
} from './api'
import { SystemStatusPage } from './SystemStatusPage'

vi.mock('../auth/api', () => ({ getCurrentSession: vi.fn() }))
vi.mock('./api', () => ({
  assignAdministrativeGroupAdministrator: vi.fn(),
  getAdministrationSnapshot: vi.fn(),
  getSystemStatus: vi.fn(),
  updateAdministrativeUserRole: vi.fn(),
  updateAdministrativeUserStatus: vi.fn(),
}))

const currentUser: AuthUser = {
  id: 'current-user',
  username: 'current-admin',
  system_role: 'admin',
  must_change_password: false,
}

const secondAdmin = {
  id: 'second-admin',
  username: 'second-admin',
  is_active: true,
  system_role: 'admin' as const,
  group_names: [],
  group_admin_group_names: [],
  active_session_count: 1,
  created_at: '2026-07-15T00:00:00Z',
}

const administration: AdministrationSnapshot = {
  users: [
    {
      id: currentUser.id,
      username: currentUser.username,
      is_active: true,
      system_role: 'admin',
      group_names: [],
      group_admin_group_names: [],
      active_session_count: 1,
      created_at: '2026-07-15T00:00:00Z',
    },
    secondAdmin,
  ],
  groups: [],
  auditEvents: [],
  maintenanceHistory: [],
}

const status = {
  alerts: [],
  storage: {
    status: 'available',
    available: true,
    writable: true,
    minimum_free_bytes: 0,
    free_bytes: 10,
    total_bytes: 20,
    active_photo_count: 1,
    active_photo_bytes: 10,
    trashed_photo_count: 0,
    trashed_photo_bytes: 0,
  },
  latest_runs: [],
} as unknown as SystemStatus

describe('SystemStatusPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSystemStatus).mockResolvedValue(status)
    vi.mocked(getAdministrationSnapshot).mockResolvedValue(administration)
    vi.mocked(updateAdministrativeUserRole).mockResolvedValue(undefined)
    vi.mocked(getCurrentSession).mockResolvedValue({ ...currentUser, system_role: 'user' })
  })

  it('refreshes the current user after changing their system role', async () => {
    const onCurrentUserChanged = vi.fn()
    const user = userEvent.setup()
    render(
      <SystemStatusPage
        currentUserId={currentUser.id}
        onUnauthorized={vi.fn()}
        onCurrentUserChanged={onCurrentUserChanged}
      />,
      { wrapper: createAppWrapper('/system') },
    )

    const row = (await screen.findByText(currentUser.username)).closest('tr')
    expect(row).not.toBeNull()
    await user.type(screen.getByLabelText('操作する管理者の現在のパスワード'), 'password')
    await user.click(within(row!).getByRole('button', { name: '一般ユーザーに変更' }))

    await waitFor(() => expect(getCurrentSession).toHaveBeenCalledOnce())
    expect(onCurrentUserChanged).toHaveBeenCalledWith({ ...currentUser, system_role: 'user' })
  })

  it('shows and retries a non-authentication administration load failure', async () => {
    const user = userEvent.setup()
    vi.mocked(getAdministrationSnapshot)
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce(administration)
    render(
      <SystemStatusPage currentUserId={currentUser.id} onUnauthorized={vi.fn()} onCurrentUserChanged={vi.fn()} />,
      { wrapper: createAppWrapper('/system') },
    )

    expect(await screen.findByText('システム状態を読み込めませんでした。')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '更新' }))
    await waitFor(() => expect(screen.getByText(currentUser.username)).toBeInTheDocument())
    expect(getAdministrationSnapshot).toHaveBeenCalledTimes(2)
  })
})
