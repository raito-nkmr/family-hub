import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import {
  getGroup,
  getGroupAdministration,
  getGroupAuditEvents,
  getGroups,
  type GroupDetail,
  type FamilyGroup,
} from './api'
import { GroupPage } from './GroupPage'

vi.mock('./api', () => ({
  addGroupMember: vi.fn(),
  createGroup: vi.fn(),
  getGroup: vi.fn(),
  getGroupAdministration: vi.fn(),
  getGroupAuditEvents: vi.fn(),
  getGroupMemberCandidates: vi.fn(),
  getGroups: vi.fn(),
  removeGroupMember: vi.fn(),
  updateGroupMemberRole: vi.fn(),
}))

describe('GroupPage', () => {
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
})
