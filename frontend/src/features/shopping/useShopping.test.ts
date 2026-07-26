import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { getGroups, type FamilyGroup } from '../groups/api'
import { createShoppingItem, getShoppingItems, purchaseShoppingItem, type ShoppingItem } from './api'
import { useShopping } from './useShopping'

vi.mock('../groups/api', () => ({ getGroups: vi.fn() }))
vi.mock('./api', () => ({
  createShoppingItem: vi.fn(),
  getShoppingItems: vi.fn(),
  purchaseShoppingItem: vi.fn(),
  restoreShoppingItem: vi.fn(),
}))

const groups = [
  { id: 'group-1', name: '同居家族' },
  { id: 'group-2', name: '拡大家族' },
] as FamilyGroup[]

function makeItem(groupId: string): ShoppingItem {
  return {
    id: `item-${groupId}`,
    group_id: groupId,
    name: groupId,
    created_by_user_id: 'user-1',
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
    purchased_by_user_id: null,
    purchased_by_username: null,
    purchased_at: null,
  }
}

describe('useShopping', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getGroups).mockResolvedValue(groups)
    vi.mocked(getShoppingItems).mockResolvedValue([])
  })

  it('keeps items for the latest group when responses arrive out of order', async () => {
    const onUnauthorized = vi.fn()
    let resolveFirst: ((value: ShoppingItem[]) => void) | undefined
    vi.mocked(getShoppingItems).mockImplementation((groupId) => {
      if (groupId === groups[0].id) return new Promise((resolve) => (resolveFirst = resolve))
      return Promise.resolve([makeItem(groupId)])
    })
    const { result } = renderHook(() => useShopping({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.selectedGroupId).toBe(groups[0].id))

    await act(() => result.current.selectGroup(groups[1].id))
    await waitFor(() => expect(result.current.items).toEqual([makeItem(groups[1].id)]))
    await act(() => {
      resolveFirst?.([makeItem(groups[0].id)])
    })

    expect(result.current.selectedGroupId).toBe(groups[1].id)
    expect(result.current.items).toEqual([makeItem(groups[1].id)])
  })

  it('restores the selected group from the URL', async () => {
    vi.mocked(getShoppingItems).mockImplementation((groupId) => Promise.resolve([makeItem(groupId)]))

    const { result } = renderHook(() => useShopping({ onUnauthorized: vi.fn() }), {
      wrapper: createAppWrapper('/shopping?group=group-2'),
    })

    await waitFor(() => expect(result.current.items).toEqual([makeItem(groups[1].id)]))
    expect(result.current.selectedGroupId).toBe(groups[1].id)
    expect(getShoppingItems).toHaveBeenCalledWith(groups[1].id, expect.any(AbortSignal))
  })

  it('clears the previous group items when loading the next group fails', async () => {
    vi.mocked(getShoppingItems).mockResolvedValueOnce([makeItem(groups[0].id)])
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useShopping({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.items).toEqual([makeItem(groups[0].id)]))
    vi.mocked(getShoppingItems).mockRejectedValueOnce(new Error('offline'))

    await act(() => result.current.selectGroup(groups[1].id))
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.selectedGroupId).toBe(groups[1].id)
    expect(result.current.items).toEqual([])
    expect(result.current.pageError).not.toBeNull()
  })

  it('does not mix an item created for the previous group into the current group', async () => {
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useShopping({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))
    let resolveCreate: ((value: ShoppingItem) => void) | undefined
    vi.mocked(createShoppingItem).mockImplementation(() => new Promise((resolve) => (resolveCreate = resolve)))
    vi.mocked(getShoppingItems).mockResolvedValueOnce([makeItem(groups[1].id)])

    let createRequest: Promise<boolean>
    act(() => {
      createRequest = result.current.addItem('牛乳')
    })
    await act(() => result.current.selectGroup(groups[1].id))
    resolveCreate?.({ ...makeItem(groups[0].id), name: '牛乳' })
    await act(() => createRequest!)

    expect(result.current.items).toEqual([makeItem(groups[1].id)])
  })

  it('tracks concurrent item updates independently', async () => {
    const first = makeItem(groups[0].id)
    const second = { ...makeItem(groups[0].id), id: 'item-2' }
    vi.mocked(getShoppingItems).mockResolvedValueOnce([first, second])
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useShopping({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.items).toHaveLength(2))
    const resolvers = new Map<string, (value: ShoppingItem) => void>()
    vi.mocked(purchaseShoppingItem).mockImplementation(
      (itemId) => new Promise((resolve) => resolvers.set(itemId, resolve)),
    )

    let firstRequest: Promise<void>
    let secondRequest: Promise<void>
    act(() => {
      firstRequest = result.current.changePurchaseState(first, true)
      secondRequest = result.current.changePurchaseState(second, true)
    })
    expect(result.current.pendingItemIds).toEqual(new Set([first.id, second.id]))

    resolvers.get(first.id)?.({ ...first, purchased_at: '2026-07-17T01:00:00Z' })
    await act(() => firstRequest!)
    expect(result.current.pendingItemIds).toEqual(new Set([second.id]))

    resolvers.get(second.id)?.({ ...second, purchased_at: '2026-07-17T01:00:00Z' })
    await act(() => secondRequest!)
    expect(result.current.pendingItemIds).toEqual(new Set())
  })
})
