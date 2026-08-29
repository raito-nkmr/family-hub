import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { createAppQueryClient } from '../../shared/api/queryClient'
import { queryKeys } from '../../shared/api/queryKeys'
import type { FamilyGroup, GroupDetail } from '../groups/api'
import { getGroup, getGroups } from '../groups/api'
import {
  getShoppingCategories,
  getShoppingRequests,
  getShoppingStatistics,
  getShoppingTrips,
  deleteShoppingTrip,
  purchaseShoppingRequest,
  reverseShoppingPurchase,
  type ShoppingPurchase,
  type ShoppingRequest,
  type ShoppingTrip,
} from './api'
import { todayInput, useShoppingHistory, useShoppingStore } from './useShoppingWorkflow'

vi.mock('../groups/api', () => ({ getGroup: vi.fn(), getGroups: vi.fn() }))
vi.mock('../../shared/ui/confirmation', () => ({ useConfirmation: vi.fn(() => async () => true) }))
vi.mock('./api', () => ({
  addUnplannedShoppingPurchase: vi.fn(),
  createShoppingCategory: vi.fn(),
  createShoppingRequest: vi.fn(),
  deleteShoppingTrip: vi.fn(),
  deleteShoppingCategory: vi.fn(),
  deleteShoppingRequest: vi.fn(),
  discardShoppingTrip: vi.fn(),
  getShoppingCategories: vi.fn(),
  getShoppingRequests: vi.fn(),
  getShoppingStatistics: vi.fn(),
  getShoppingTrips: vi.fn(),
  purchaseShoppingRequest: vi.fn(),
  reorderShoppingCategories: vi.fn(),
  reverseShoppingPurchase: vi.fn(),
  startShoppingTrip: vi.fn(),
  updateShoppingCategory: vi.fn(),
  updateShoppingPurchase: vi.fn(),
  updateShoppingRequest: vi.fn(),
  updateShoppingTrip: vi.fn(),
}))

const groups: FamilyGroup[] = [
  {
    id: 'group-1',
    name: '同居家族',
    created_by_user_id: 'user-1',
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    current_user_role: 'admin',
    member_count: 1,
    timezone: 'Asia/Tokyo',
  },
  {
    id: 'group-2',
    name: '拡大家族',
    created_by_user_id: 'user-1',
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
    current_user_role: 'admin',
    member_count: 1,
    timezone: 'America/Los_Angeles',
  },
]

const groupDetails: Record<string, GroupDetail> = {
  'group-1': {
    ...groups[0],
    members: [],
  },
  'group-2': {
    ...groups[1],
    members: [],
  },
}

const item: ShoppingRequest = {
  id: 'item-1',
  group_id: 'group-1',
  name: '牛乳',
  created_by_user_id: 'user-1',
  created_at: '2026-07-14T00:00:00Z',
  updated_at: '2026-07-14T00:00:00Z',
  assignee_user_id: null,
  assignee_username: null,
  category_id: null,
  category_name: null,
}

const purchase: ShoppingPurchase = {
  id: 'purchase-1',
  trip_id: 'trip-1',
  shopping_item_id: item.id,
  item_name: item.name,
  assignee_user_id: null,
  assignee_username: null,
  category_id: null,
  category_name: null,
  purchased_by_user_id: 'user-1',
  purchased_by_username: '家族',
  purchased_at: '2026-07-14T01:00:00Z',
  reversed_at: null,
  reversed_by_user_id: null,
}

function makeWrapper(queryClient = createAppQueryClient()) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    )
  }
}

describe('useShoppingWorkflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    localStorage.clear()
    vi.mocked(getGroups).mockResolvedValue(groups)
    vi.mocked(getGroup).mockImplementation((groupId) => Promise.resolve(groupDetails[groupId]))
    vi.mocked(getShoppingRequests).mockResolvedValue([item])
    vi.mocked(getShoppingTrips).mockResolvedValue({ items: [], next_cursor: null })
    vi.mocked(getShoppingCategories).mockResolvedValue([])
    vi.mocked(getShoppingStatistics).mockResolvedValue({
      group_id: 'group-1',
      from_date: '2026-01-01',
      to_date: '2026-07-15',
      purchase_count: 0,
      planned_purchase_count: 0,
      monthly: [],
      categories: [],
      assignees: [],
      purchasers: [],
      total_amount_yen: 0,
      trip_count: 0,
      unplanned_purchase_count: 0,
      unrecorded_trip_count: 0,
    })
    vi.mocked(purchaseShoppingRequest).mockResolvedValue(purchase)
    vi.mocked(reverseShoppingPurchase).mockResolvedValue(purchase)
  })

  it('stops loading when the user has no shopping group', async () => {
    vi.mocked(getGroups).mockResolvedValue([])

    const { result } = renderHook(() => useShoppingStore({ onUnauthorized: vi.fn() }), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.groups).toEqual([])
    expect(getShoppingRequests).not.toHaveBeenCalled()
    expect(getShoppingTrips).not.toHaveBeenCalled()
  })

  it('clears undo on group switch and invalidates the purchase group', async () => {
    const queryClient = createAppQueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useShoppingStore({ onUnauthorized: vi.fn() }), {
      wrapper: makeWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.selectedGroupId).toBe('group-1'))
    await act(() => result.current.purchase(item))
    await waitFor(() => expect(result.current.lastPurchase?.groupId).toBe('group-1'))

    await act(() => result.current.undo())

    expect(reverseShoppingPurchase).toHaveBeenCalledWith(purchase.id)
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.shoppingTrips('group-1') })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.shoppingRequests('group-1') })

    await act(() => result.current.selectGroup('group-2'))

    expect(result.current.lastPurchase).toBeNull()
  })

  it('uses the selected group timezone for dates and resets them after switching groups', async () => {
    const fixedDate = new Date('2026-07-15T00:30:00Z')
    expect(todayInput('Asia/Tokyo', fixedDate)).toBe('2026-07-15')
    expect(todayInput('America/Los_Angeles', fixedDate)).toBe('2026-07-14')
    const firstGroupToday = todayInput('Asia/Tokyo')
    const secondGroupToday = todayInput('America/Los_Angeles')
    const currentYear = new Date().getFullYear().toString()

    const { result } = renderHook(() => useShoppingHistory({ onUnauthorized: vi.fn() }), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.selectedGroupId).toBe('group-1'))
    await waitFor(() => {
      expect(result.current.toDate).toBe(firstGroupToday)
      expect(result.current.fromDate).toBe(`${currentYear}-01-01`)
    })

    await act(() => result.current.selectGroup('group-2'))
    await waitFor(() => expect(result.current.selectedGroupId).toBe('group-2'))
    await waitFor(() => {
      expect(result.current.toDate).toBe(secondGroupToday)
      expect(result.current.fromDate).toBe(`${currentYear}-01-01`)
    })
  })

  it('hides discarded trips by default and refetches them when enabled', async () => {
    const { result } = renderHook(() => useShoppingHistory({ onUnauthorized: vi.fn() }), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.selectedGroupId).toBe('group-1'))
    expect(result.current.includeDiscarded).toBe(false)
    expect(vi.mocked(getShoppingTrips).mock.calls.at(-1)?.[4]).toBe(false)

    await act(() => result.current.setIncludeDiscarded(true))

    await waitFor(() => expect(result.current.includeDiscarded).toBe(true))
    expect(vi.mocked(getShoppingTrips).mock.calls.at(-1)?.[4]).toBe(true)
  })

  it('removes a deleted finished trip from history and refreshes related queries', async () => {
    const queryClient = createAppQueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const trip: ShoppingTrip = {
      id: 'trip-1',
      group_id: 'group-1',
      started_by_user_id: 'user-1',
      started_by_username: '家族',
      started_at: '2026-07-15T01:00:00Z',
      finalized_at: '2026-07-15T02:00:00Z',
      discarded_at: null,
      discarded_by_user_id: null,
      discarded_by_username: null,
      total_amount_yen: 1000,
      recorded_by_user_id: 'user-1',
      recorded_by_username: '家族',
      updated_at: '2026-07-15T02:00:00Z',
      purchase_count: 1,
      active_purchase_count: 1,
      purchases: [],
    }
    vi.mocked(deleteShoppingTrip).mockResolvedValue(undefined)
    const { result } = renderHook(() => useShoppingHistory({ onUnauthorized: vi.fn() }), {
      wrapper: makeWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.selectedGroupId).toBe('group-1'))
    await act(async () => {
      expect(await result.current.deleteTrip(trip)).toBe(true)
    })

    expect(deleteShoppingTrip).toHaveBeenCalledWith(trip.id, expect.anything())
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.shoppingTripHistory('group-1') })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.shoppingRequests('group-1') })
  })
})
