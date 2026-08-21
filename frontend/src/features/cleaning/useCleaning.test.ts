import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LAST_SELECTED_GROUP_STORAGE_KEY } from '../../shared/routing/useGroupSelection'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { getGroups, type FamilyGroup } from '../groups/api'
import { getCleaningCategories, getCleaningTasks, type CleaningTask } from './api'
import { useCleaning } from './useCleaning'

vi.mock('../groups/api', () => ({ getGroups: vi.fn() }))
vi.mock('./api', () => ({
  completeCleaningTask: vi.fn(),
  createCleaningCategory: vi.fn(),
  createCleaningTask: vi.fn(),
  deleteCleaningCategory: vi.fn(),
  getCleaningCategories: vi.fn(),
  getCleaningTasks: vi.fn(),
  updateCleaningCategory: vi.fn(),
  updateCleaningTask: vi.fn(),
}))

const groups = [
  { id: 'group-1', name: '同居家族' },
  { id: 'group-2', name: '拡大家族' },
] as FamilyGroup[]

function makeTask(groupId: string): CleaningTask {
  return {
    id: `task-${groupId}`,
    group_id: groupId,
    name: groupId,
    category_id: 'cleaning-id',
    interval_days: 1,
    is_active: true,
    created_by_user_id: 'user-1',
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
    next_due_at: '2026-07-18T00:00:00Z',
    current_user_role: 'admin',
    last_completion: null,
  }
}

describe('useCleaning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem(LAST_SELECTED_GROUP_STORAGE_KEY)
    vi.mocked(getGroups).mockResolvedValue(groups)
    vi.mocked(getCleaningCategories).mockResolvedValue([])
    vi.mocked(getCleaningTasks).mockResolvedValue([])
  })

  it('keeps tasks for the latest group when responses arrive out of order', async () => {
    const onUnauthorized = vi.fn()
    let resolveFirst: ((value: CleaningTask[]) => void) | undefined
    vi.mocked(getCleaningTasks).mockImplementation((groupId) => {
      if (groupId === groups[0].id) return new Promise((resolve) => (resolveFirst = resolve))
      return Promise.resolve([makeTask(groupId)])
    })
    const { result } = renderHook(() => useCleaning({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.selectedGroupId).toBe(groups[0].id))

    await act(() => result.current.selectGroup(groups[1].id))
    await waitFor(() => expect(result.current.tasks).toEqual([makeTask(groups[1].id)]))
    await act(() => {
      resolveFirst?.([makeTask(groups[0].id)])
    })

    expect(result.current.selectedGroupId).toBe(groups[1].id)
    expect(result.current.tasks).toEqual([makeTask(groups[1].id)])
  })

  it('clears the previous group tasks when loading the next group fails', async () => {
    vi.mocked(getCleaningTasks).mockResolvedValueOnce([makeTask(groups[0].id)])
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useCleaning({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.tasks).toEqual([makeTask(groups[0].id)]))
    vi.mocked(getCleaningTasks).mockRejectedValueOnce(new Error('offline'))

    await act(() => result.current.selectGroup(groups[1].id))
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.selectedGroupId).toBe(groups[1].id)
    expect(result.current.tasks).toEqual([])
    expect(result.current.pageError).not.toBeNull()
  })
})
