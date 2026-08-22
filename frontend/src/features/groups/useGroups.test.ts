import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import {
  addGroupMember,
  createGroup,
  getGroup,
  getGroups,
  renameGroup,
  updateGroupTimezone,
  updateGroupMemberRole,
  type GroupDetail,
  type GroupMember,
} from './api'
import { useGroups } from './useGroups'

vi.mock('./api', () => ({
  addGroupMember: vi.fn(),
  createGroup: vi.fn(),
  getGroup: vi.fn(),
  getGroupMemberCandidates: vi.fn(),
  getGroups: vi.fn(),
  renameGroup: vi.fn(),
  updateGroupTimezone: vi.fn(),
  removeGroupMember: vi.fn(),
  updateGroupMemberRole: vi.fn(),
}))

const group: GroupDetail = {
  id: 'group-1',
  name: '同居家族',
  created_by_user_id: 'user-1',
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T00:00:00Z',
  current_user_role: 'admin',
  member_count: 1,
  timezone: 'Asia/Tokyo',
  members: [],
}

const firstMember: GroupMember = {
  user_id: 'user-2',
  username: 'first',
  role: 'member',
  joined_at: '2026-07-15T00:00:00Z',
  is_active: true,
}

const secondMember: GroupMember = { ...firstMember, user_id: 'user-3', username: 'second' }

describe('useGroups', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(getGroups).mockResolvedValue([])
  })

  it('adds and selects a newly created group', async () => {
    vi.mocked(createGroup).mockResolvedValue(group)
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.create(group.name))

    expect(result.current.groups).toEqual([group])
    expect(result.current.selectedGroup).toEqual(group)
  })

  it('shows a specific error when the group name already exists', async () => {
    vi.mocked(createGroup).mockRejectedValue(new ApiError(409, 'Conflict'))
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.create(group.name))

    expect(result.current.dialogError).toBe('同名のグループが既に存在します。')
  })

  it('keeps the most recently opened group when responses arrive out of order', async () => {
    const secondGroup = { ...group, id: 'group-2', name: '拡大家族' }
    let resolveFirst: ((value: GroupDetail) => void) | undefined
    vi.mocked(getGroup).mockImplementation((groupId) => {
      if (groupId === group.id) return new Promise((resolve) => (resolveFirst = resolve))
      return Promise.resolve(secondGroup)
    })
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))

    let firstRequest: Promise<void>
    act(() => {
      firstRequest = result.current.openGroup(group)
    })
    await act(() => result.current.openGroup(secondGroup))
    resolveFirst?.(group)
    await act(() => firstRequest!)

    expect(result.current.selectedGroup).toEqual(secondGroup)
  })

  it('serializes member changes and reloads the authoritative group state', async () => {
    const initial = { ...group, members: [firstMember, secondMember], member_count: 2 }
    const latest = {
      ...initial,
      members: [{ ...firstMember, role: 'admin' as const }, secondMember],
    }
    let resolveChange: ((value: GroupDetail) => void) | undefined
    vi.mocked(getGroup).mockResolvedValueOnce(initial).mockResolvedValueOnce(latest)
    vi.mocked(updateGroupMemberRole).mockImplementation(() => new Promise((resolve) => (resolveChange = resolve)))
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized }), {
      wrapper: createAppWrapper(),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))
    await act(() => result.current.openGroup(initial))

    let firstChange: Promise<void>
    act(() => {
      firstChange = result.current.changeRole(firstMember, 'admin')
      void result.current.changeRole(secondMember, 'admin')
    })
    expect(updateGroupMemberRole).toHaveBeenCalledOnce()
    resolveChange?.(initial)
    await act(() => firstChange!)

    expect(getGroup).toHaveBeenCalledTimes(2)
    expect(result.current.selectedGroup).toEqual(latest)
  })

  it('restores the open group from the URL', async () => {
    vi.mocked(getGroup).mockResolvedValue(group)
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    await waitFor(() => expect(result.current.selectedGroup).toEqual(group))
    expect(getGroup).toHaveBeenCalledWith(group.id, expect.any(AbortSignal))
  })

  it('keeps a successful invitation successful when refreshing the group fails', async () => {
    vi.mocked(getGroup).mockResolvedValueOnce(group).mockRejectedValue(new Error('refresh failed'))
    vi.mocked(addGroupMember).mockResolvedValue({
      id: 'invitation-1',
      group_id: group.id,
      group_name: group.name,
      invitee_user_id: 'user-2',
      username: 'new member',
      role: 'member',
      status: 'pending',
      created_at: '2026-07-15T00:00:00Z',
    })
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    await waitFor(() => expect(result.current.selectedGroup).toEqual(group))
    await act(() => result.current.addMember('user-2', 'member'))
    await waitFor(() => expect(vi.mocked(getGroup).mock.calls.length).toBeGreaterThan(1))

    expect(addGroupMember).toHaveBeenCalledWith(group.id, 'user-2', 'member')
    expect(result.current.dialogError).toBeNull()
  })

  it('reports a failed group rename without claiming success', async () => {
    vi.mocked(getGroup).mockResolvedValue(group)
    vi.mocked(renameGroup).mockRejectedValue(new Error('rename failed'))
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    await waitFor(() => expect(result.current.selectedGroup).toEqual(group))
    let renamed: boolean | undefined
    await act(async () => {
      renamed = await result.current.rename('新しい名前')
    })

    expect(renamed).toBe(false)
    expect(result.current.pageError).toBe('グループ名を変更できませんでした。')
  })

  it('updates the group time zone', async () => {
    vi.mocked(getGroup).mockResolvedValue(group)
    vi.mocked(updateGroupTimezone).mockResolvedValue({ ...group, timezone: 'Europe/London' })
    const { result } = renderHook(() => useGroups({ currentUserId: 'user-1', onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper('/groups?group=group-1'),
    })

    await waitFor(() => expect(result.current.selectedGroup).toEqual(group))
    await act(() => result.current.updateTimezone('Europe/London'))

    expect(updateGroupTimezone).toHaveBeenCalledWith(group.id, 'Europe/London')
    expect(result.current.selectedGroup?.timezone).toBe('Europe/London')
  })
})
