import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ShoppingPurchase, ShoppingRequest, ShoppingTrip } from './api'
import { ShoppingPage } from './ShoppingPage'

const purchase = vi.fn()
const undo = vi.fn()
const beginTrip = vi.fn()
const endTrip = vi.fn()
const discardTrip = vi.fn()
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

const activeTrip: ShoppingTrip = {
  id: 'trip-id',
  group_id: 'group-id',
  started_by_user_id: 'user-id',
  started_by_username: '家族メンバー',
  started_at: '2026-07-15T01:00:00Z',
  finalized_at: null,
  discarded_at: null,
  discarded_by_user_id: null,
  discarded_by_username: null,
  total_amount_yen: null,
  recorded_by_user_id: null,
  recorded_by_username: null,
  updated_at: '2026-07-15T01:00:00Z',
  purchase_count: 0,
  active_purchase_count: 0,
  purchases: [],
}

describe('ShoppingPage', () => {
  beforeEach(() => {
    purchase.mockReset()
    undo.mockReset()
    beginTrip.mockReset()
    endTrip.mockReset()
    discardTrip.mockReset()
    useShoppingStore.mockReturnValue({
      groups: [{ id: 'group-id', name: '同居家族' }],
      selectedGroupId: 'group-id',
      items: [item],
      loading: false,
      submitting: false,
      pendingItemIds: new Set<string>(),
      pageError: null,
      lastPurchase: null,
      activeTrip: null,
      selectGroup: vi.fn(),
      purchase,
      undo,
      beginTrip,
      endTrip,
      discardTrip,
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

  it('starts a trip when there is no active trip', async () => {
    const user = userEvent.setup()
    render(<ShoppingPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '今回の買い物を開始' }))

    expect(beginTrip).toHaveBeenCalledOnce()
  })

  it('switches the store control to finish while a trip is active', async () => {
    const user = userEvent.setup()
    useShoppingStore.mockReturnValueOnce({
      ...useShoppingStore(),
      activeTrip,
    })
    render(<ShoppingPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '今回の買い物を終了' }))

    expect(endTrip).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: '今回の買い物を開始' })).not.toBeInTheDocument()
  })
})
