import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { getCleaningTasks } from '../cleaning/api'
import { getGroups } from '../groups/api'
import { getPhotos } from '../photos/api'
import { getShoppingItems } from '../shopping/api'
import { useHome } from './useHome'

vi.mock('../cleaning/api', () => ({ getCleaningTasks: vi.fn() }))
vi.mock('../groups/api', () => ({ getGroups: vi.fn() }))
vi.mock('../photos/api', () => ({ getPhotos: vi.fn() }))
vi.mock('../shopping/api', () => ({ getShoppingItems: vi.fn() }))

describe('useHome', () => {
  beforeEach(() => {
    vi.mocked(getGroups).mockResolvedValue([{ id: 'group-id', name: '同居家族' }] as never)
    vi.mocked(getCleaningTasks).mockResolvedValue([
      { id: 'active-task', group_id: 'group-id', is_active: true },
      { id: 'inactive-task', group_id: 'group-id', is_active: false },
    ] as never)
    vi.mocked(getShoppingItems).mockResolvedValue([
      { id: 'active-item', group_id: 'group-id', purchased_at: null },
      { id: 'purchased-item', group_id: 'group-id', purchased_at: '2026-07-16T00:00:00Z' },
    ] as never)
    vi.mocked(getPhotos).mockResolvedValue({ items: [], next_cursor: null, total_count: 0 })
  })

  it('loads active tasks and unpurchased items for all groups', async () => {
    const { result } = renderHook(() => useHome({ userId: 'user-id', active: true, onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.cleaningTasks.map(({ task }) => task.id)).toEqual(['active-task'])
    expect(result.current.shoppingItems.map(({ item }) => item.id)).toEqual(['active-item'])
    expect(getPhotos).toHaveBeenCalledWith({}, undefined, expect.any(AbortSignal), 4)
  })

  it('keeps successful home sections when another section fails', async () => {
    vi.mocked(getCleaningTasks).mockRejectedValue(new Error('cleaning unavailable'))
    const { result } = renderHook(() => useHome({ userId: 'user-id', active: true, onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.groups).toHaveLength(1)
    expect(result.current.cleaningTasks).toEqual([])
    expect(result.current.shoppingItems.map(({ item }) => item.id)).toEqual(['active-item'])
    expect(result.current.error).not.toBeNull()
  })
})
