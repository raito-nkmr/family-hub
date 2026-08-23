import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ShoppingTrip } from './api'
import { ShoppingHistoryPage } from './ShoppingHistoryPage'

const saveTripAmount = vi.fn()
const deleteTrip = vi.fn()
const setIncludeDiscarded = vi.fn()
const useShoppingHistory = vi.fn()

vi.mock('./useShoppingWorkflow', () => ({
  useShoppingHistory: () => useShoppingHistory(),
}))

const trip: ShoppingTrip = {
  id: 'trip-id',
  group_id: 'group-id',
  started_by_user_id: 'user-id',
  started_by_username: '家族メンバー',
  started_at: '2026-07-15T01:00:00Z',
  finalized_at: null,
  discarded_at: null,
  discarded_by_user_id: null,
  discarded_by_username: null,
  total_amount_yen: 1200,
  recorded_by_user_id: null,
  recorded_by_username: null,
  updated_at: '2026-07-15T02:00:00Z',
  purchase_count: 0,
  active_purchase_count: 0,
  purchases: [],
}

describe('ShoppingHistoryPage', () => {
  beforeEach(() => {
    saveTripAmount.mockReset()
    saveTripAmount.mockResolvedValue(true)
    deleteTrip.mockReset()
    setIncludeDiscarded.mockReset()
    useShoppingHistory.mockReturnValue({
      groups: [{ id: 'group-id', name: '同居家族' }],
      selectedGroupId: 'group-id',
      loading: false,
      submitting: false,
      pageError: null,
      fromDate: '2026-01-01',
      toDate: '2026-07-15',
      trips: [trip],
      hasMore: false,
      loadingMore: false,
      statistics: null,
      categories: [],
      members: [],
      selectGroup: vi.fn(),
      setFromDate: vi.fn(),
      setToDate: vi.fn(),
      saveTripAmount,
      deleteTrip,
      includeDiscarded: false,
      setIncludeDiscarded,
      addUnplanned: vi.fn(),
      updatePurchase: vi.fn(),
      reversePurchase: vi.fn(),
      loadMore: vi.fn(),
      refresh: vi.fn(),
    })
  })

  it('allows a trip to remain unrecorded when the amount is unknown', async () => {
    const user = userEvent.setup()
    render(<ShoppingHistoryPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '金額不明のままにする' }))

    expect(saveTripAmount).toHaveBeenCalledWith('trip-id', null)
  })

  it('shows discarded trips without amount editing controls', () => {
    useShoppingHistory.mockReturnValueOnce({
      ...useShoppingHistory(),
      trips: [{ ...trip, discarded_at: '2026-07-15T03:00:00Z', finalized_at: null }],
    })
    render(<ShoppingHistoryPage onUnauthorized={vi.fn()} />)

    expect(screen.getByText('破棄済み')).toBeInTheDocument()
    expect(screen.queryByLabelText('買い物全体の金額（円）')).not.toBeInTheDocument()
  })

  it('allows deleting a finished trip from history', async () => {
    const user = userEvent.setup()
    const finishedTrip = {
      ...trip,
      finalized_at: '2026-07-15T03:00:00Z',
      purchase_count: 1,
      active_purchase_count: 1,
    }
    useShoppingHistory.mockReturnValueOnce({
      ...useShoppingHistory(),
      trips: [finishedTrip],
    })

    render(<ShoppingHistoryPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '買い物を削除' }))

    expect(deleteTrip).toHaveBeenCalledWith(finishedTrip)
  })

  it('keeps discarded trips hidden by default and allows showing them', async () => {
    const user = userEvent.setup()
    render(<ShoppingHistoryPage onUnauthorized={vi.fn()} />)

    const toggle = screen.getByRole('checkbox', { name: '破棄済みの買い物を表示' })
    expect(toggle).not.toBeChecked()
    await user.click(toggle)

    expect(setIncludeDiscarded).toHaveBeenCalledWith(true)
  })
})
