import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ShoppingPurchase, ShoppingRequest } from './api'
import { ShoppingPage } from './ShoppingPage'

const purchase = vi.fn()
const undo = vi.fn()
const useShoppingStore = vi.fn()

vi.mock('./useShoppingWorkflow', () => ({
  useShoppingStore: () => useShoppingStore(),
}))

const item: ShoppingRequest = {
  id: 'item-id',
  group_id: 'group-id',
  name: '牛乳 2本',
  created_by_user_id: 'requester-id',
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T01:00:00Z',
  assignee_user_id: 'assignee-id',
  assignee_username: '家族メンバー',
  category_id: null,
  category_name: null,
}

const purchaseRecord: ShoppingPurchase = {
  id: 'purchase-id',
  trip_id: 'trip-id',
  shopping_item_id: item.id,
  item_name: item.name,
  assignee_user_id: item.assignee_user_id,
  assignee_username: item.assignee_username,
  category_id: null,
  category_name: null,
  purchased_by_user_id: 'buyer-id',
  purchased_by_username: '買った人',
  purchased_at: '2026-07-15T01:00:00Z',
  reversed_at: null,
  reversed_by_user_id: null,
}

describe('ShoppingPage', () => {
  beforeEach(() => {
    purchase.mockReset()
    undo.mockReset()
    useShoppingStore.mockReturnValue({
      groups: [{ id: 'group-id', name: '同居家族' }],
      selectedGroupId: 'group-id',
      items: [item],
      loading: false,
      submitting: false,
      pendingItemIds: new Set<string>(),
      pageError: null,
      lastPurchase: null,
      selectGroup: vi.fn(),
      purchase,
      undo,
      beginTrip: vi.fn(),
      refresh: vi.fn(),
    })
  })

  it('completes a purchase with one tap and shows no confirmation', async () => {
    const user = userEvent.setup()
    render(<ShoppingPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '牛乳 2本を購入済みにする' }))

    expect(purchase).toHaveBeenCalledWith(item)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('offers an immediate undo for the latest purchase', async () => {
    const user = userEvent.setup()
    useShoppingStore.mockReturnValueOnce({
      ...useShoppingStore(),
      items: [],
      lastPurchase: purchaseRecord,
    })
    render(<ShoppingPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '取り消す' }))

    expect(undo).toHaveBeenCalledOnce()
  })
})
