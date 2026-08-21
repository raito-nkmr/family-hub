import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import {
  decideGroupMembershipInvitation,
  getGroup,
  getGroupAdministration,
  getGroupAuditEvents,
  getGroups,
  getMyGroupMembershipInvitations,
  renameGroup,
  updateGroupTimezone,
  type GroupDetail,
  type FamilyGroup,
} from './api'
import { GroupPage } from './GroupPage'

vi.mock('./api', () => ({
  addGroupMember: vi.fn(),
  createGroup: vi.fn(),
  decideGroupMembershipInvitation: vi.fn(),
  getGroup: vi.fn(),
  getGroupAdministration: vi.fn(),
  getGroupAuditEvents: vi.fn(),
  getGroupMemberCandidates: vi.fn(),
  getGroups: vi.fn(),
  getMyGroupMembershipInvitations: vi.fn(),
  renameGroup: vi.fn(),
  updateGroupTimezone: vi.fn(),
  removeGroupMember: vi.fn(),
  updateGroupMemberRole: vi.fn(),
}))

describe('GroupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getMyGroupMembershipInvitations).mockResolvedValue([])
  })

  it('returns control to the app when the session expires', async () => {
    vi.mocked(getGroups).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()

    render(<GroupPage currentUserId="current-user" onUnauthorized={onUnauthorized} />, {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })

  it('returns control to the app when administration information expires', async () => {
    const group: FamilyGroup = {
      id: 'group-1',
      name: '同居家族',
      created_by_user_id: 'user-1',
      created_at: '2026-07-15T00:00:00Z',
      updated_at: '2026-07-15T00:00:00Z',
      current_user_role: 'admin',
      member_count: 0,
      timezone: 'Asia/Tokyo',
    }
    const detail: GroupDetail = { ...group, members: [] }
    vi.mocked(getGroups).mockResolvedValue([group])
    vi.mocked(getGroup).mockResolvedValue(detail)
    vi.mocked(getGroupAdministration).mockRejectedValue(new ApiError(401, 'expired'))
    vi.mocked(getGroupAuditEvents).mockResolvedValue([])
    const onUnauthorized = vi.fn()

    render(<GroupPage currentUserId="user-1" onUnauthorized={onUnauthorized} />, {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })

  it('shows non-authentication failures inside the group administration page', async () => {
    const group: FamilyGroup = {
      id: 'group-1',
      name: '同居家族',
      created_by_user_id: 'user-1',
      created_at: '2026-07-15T00:00:00Z',
      updated_at: '2026-07-15T00:00:00Z',
      current_user_role: 'admin',
      member_count: 0,
      timezone: 'Asia/Tokyo',
    }
    const detail: GroupDetail = { ...group, members: [] }
    vi.mocked(getGroups).mockResolvedValue([group])
    vi.mocked(getGroup).mockResolvedValue(detail)
    vi.mocked(getGroupAdministration).mockRejectedValue(new ApiError(503, 'unavailable'))
    vi.mocked(getGroupAuditEvents).mockRejectedValue(new ApiError(503, 'unavailable'))

    render(<GroupPage currentUserId="user-1" onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    await waitFor(() => expect(screen.getByText('グループ管理情報を読み込めませんでした。')).toBeInTheDocument())
    expect(screen.getByText('グループの監査ログを読み込めませんでした。')).toBeInTheDocument()
  })

  it('keeps the rename input after the rename request fails', async () => {
    const group: FamilyGroup = {
      id: 'group-1',
      name: '同居家族',
      created_by_user_id: 'user-1',
      created_at: '2026-07-15T00:00:00Z',
      updated_at: '2026-07-15T00:00:00Z',
      current_user_role: 'admin',
      member_count: 0,
      timezone: 'Asia/Tokyo',
    }
    vi.mocked(getGroups).mockResolvedValue([group])
    vi.mocked(getGroup).mockResolvedValue({ ...group, members: [] })
    vi.mocked(getGroupAdministration).mockRejectedValue(new ApiError(503, 'unavailable'))
    vi.mocked(getGroupAuditEvents).mockRejectedValue(new ApiError(503, 'unavailable'))
    vi.mocked(renameGroup).mockRejectedValue(new ApiError(503, 'unavailable'))
    const user = userEvent.setup()

    render(<GroupPage currentUserId="user-1" onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    const input = await screen.findByLabelText('グループ名を変更')
    await user.type(input, '新しい名前')
    await user.click(screen.getAllByRole('button', { name: '保存する' })[0])

    await waitFor(() => expect(screen.getByText('グループ名を変更できませんでした。')).toBeInTheDocument())
    expect(input).toHaveValue('新しい名前')
  })

  it('lets an administrator update the report time zone', async () => {
    const group: FamilyGroup = {
      id: 'group-1',
      name: '同居家族',
      created_by_user_id: 'user-1',
      created_at: '2026-07-15T00:00:00Z',
      updated_at: '2026-07-15T00:00:00Z',
      current_user_role: 'admin',
      member_count: 0,
      timezone: 'Asia/Tokyo',
    }
    vi.mocked(getGroups).mockResolvedValue([group])
    vi.mocked(getGroup).mockResolvedValue({ ...group, members: [] })
    vi.mocked(getGroupAdministration).mockResolvedValue({
      album_count: 0,
      chore_task_count: 0,
      shared_photo_count: 0,
      shopping_item_count: 0,
      active_admin_count: 1,
    })
    vi.mocked(getGroupAuditEvents).mockResolvedValue([])
    vi.mocked(updateGroupTimezone).mockResolvedValue({ ...group, timezone: 'Europe/London', members: [] })
    const user = userEvent.setup()

    render(<GroupPage currentUserId="user-1" onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    const timezone = await screen.findByLabelText('レポートのタイムゾーン')
    await user.selectOptions(timezone, 'Europe/London')
    const saveButtons = screen.getAllByRole('button', { name: '保存する' })
    await user.click(saveButtons[1])

    await waitFor(() => expect(updateGroupTimezone).toHaveBeenCalledWith('group-1', 'Europe/London'))
  })

  it('returns control to the app when membership invitations expire', async () => {
    vi.mocked(getMyGroupMembershipInvitations).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()

    render(<GroupPage currentUserId="current-user" onUnauthorized={onUnauthorized} />, {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })

  it('shows a message when membership invitations cannot be loaded', async () => {
    vi.mocked(getGroups).mockResolvedValue([])
    vi.mocked(getMyGroupMembershipInvitations).mockRejectedValue(new ApiError(503, 'unavailable'))

    render(<GroupPage currentUserId="current-user" onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(screen.getByText('招待を読み込めませんでした。')).toBeInTheDocument())
  })

  it('shows a message when accepting an invitation fails', async () => {
    vi.mocked(getGroups).mockResolvedValue([])
    vi.mocked(getMyGroupMembershipInvitations).mockResolvedValue([
      {
        id: 'invitation-1',
        group_id: 'group-1',
        group_name: '同居家族',
        user_id: 'current-user',
        username: 'current-user',
        role: 'member',
        status: 'pending',
        created_at: '2026-07-15T00:00:00Z',
      },
    ])
    vi.mocked(decideGroupMembershipInvitation).mockRejectedValue(new ApiError(503, 'unavailable'))
    const user = userEvent.setup()

    render(<GroupPage currentUserId="current-user" onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper(),
    })

    await user.click(await screen.findByRole('button', { name: '承認' }))
    await waitFor(() => expect(screen.getByText('グループ招待を承認または辞退できませんでした。')).toBeInTheDocument())
  })

  it('returns control to the app when accepting an invitation expires', async () => {
    vi.mocked(getMyGroupMembershipInvitations).mockResolvedValue([
      {
        id: 'invitation-1',
        group_id: 'group-1',
        group_name: '同居家族',
        user_id: 'current-user',
        username: 'current-user',
        role: 'member',
        status: 'pending',
        created_at: '2026-07-15T00:00:00Z',
      },
    ])
    vi.mocked(decideGroupMembershipInvitation).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()
    const user = userEvent.setup()

    render(<GroupPage currentUserId="current-user" onUnauthorized={onUnauthorized} />, {
      wrapper: createAppWrapper(),
    })

    await user.click(await screen.findByRole('button', { name: '承認' }))
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })
})
