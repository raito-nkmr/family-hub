import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ShoppingItem } from './api'
import { ShoppingPage } from './ShoppingPage'

const addItem = vi.fn()
const changePurchaseState = vi.fn()
const useShopping = vi.fn()

vi.mock('./useShopping', () => ({
  useShopping: () => useShopping(),
}))

function makeItem(purchased = false): ShoppingItem {
  return {
    id: purchased ? 'purchased-item-id' : 'active-item-id',
    group_id: 'group-id',
    name: purchased ? 'パン' : '牛乳 2本',
    created_by_user_id: 'user-id',
    created_at: '2026-07-15T00:00:00Z',
    updated_at: '2026-07-15T01:00:00Z',
    purchased_by_user_id: purchased ? 'buyer-id' : null,
    purchased_by_username: purchased ? 'family-member' : null,
    purchased_at: purchased ? '2026-07-15T01:00:00Z' : null,
  }
}

describe('ShoppingPage', () => {
  beforeEach(() => {
    addItem.mockReset().mockResolvedValue(true)
    changePurchaseState.mockReset()
    useShopping.mockReturnValue({
      groups: [{ id: 'group-id', name: '同居家族' }],
      selectedGroupId: 'group-id',
      items: [makeItem(), makeItem(true)],
      loading: false,
      submitting: false,
      pendingItemIds: new Set<string>(),
      pageError: null,
      formError: null,
      selectGroup: vi.fn(),
      addItem,
      changePurchaseState,
      refresh: vi.fn(),
    })
  })

  it('adds an item with the quick entry form', async () => {
    const user = userEvent.setup()
    render(<ShoppingPage onUnauthorized={vi.fn()} />)

    await user.type(screen.getByLabelText('買うもの'), '卵 10個')
    await user.click(screen.getByRole('button', { name: 'リストに追加' }))

    expect(addItem).toHaveBeenCalledWith('卵 10個')
    expect(screen.getByLabelText('買うもの')).toHaveValue('')
  })

  it('marks an active item as purchased and can restore recent items', async () => {
    const user = userEvent.setup()
    render(<ShoppingPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '牛乳 2本を購入済みにする' }))
    await user.click(screen.getByText('最近の購入済み（1件）'))
    await user.click(screen.getByRole('button', { name: 'リストに戻す' }))

    expect(changePurchaseState).toHaveBeenNthCalledWith(1, expect.objectContaining({ id: 'active-item-id' }), true)
    expect(changePurchaseState).toHaveBeenNthCalledWith(2, expect.objectContaining({ id: 'purchased-item-id' }), false)
  })
})
