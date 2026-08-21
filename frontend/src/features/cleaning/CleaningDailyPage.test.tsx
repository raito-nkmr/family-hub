import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { useLocation } from 'react-router'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { CleaningDailyPage } from './CleaningDailyPage'

const useCleaningReport = vi.fn()

vi.mock('./useCleaningReport', () => ({
  useCleaningReport: () => useCleaningReport(),
}))

const report = {
  group_id: 'group-1',
  month: '2026-07',
  timezone: 'Asia/Tokyo',
  summary: { completion_count: 4, unique_task_count: 2, participant_count: 2, category_count: 1 },
  daily: [
    { day: '2026-07-01', completion_count: 2, unique_task_count: 1 },
    { day: '2026-07-02', completion_count: 0, unique_task_count: 0 },
    { day: '2026-07-31', completion_count: 2, unique_task_count: 1 },
  ],
  categories: [],
  members: [],
  tasks: [],
}

function makeState() {
  return {
    groups: [
      {
        id: 'group-1',
        name: '同居家族',
        created_by_user_id: 'user-1',
        created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
        current_user_role: 'member' as const,
        member_count: 2,
        timezone: 'Asia/Tokyo',
      },
    ],
    selectedGroupId: 'group-1',
    selectedGroup: { id: 'group-1', timezone: 'Asia/Tokyo' },
    report,
    month: '2026-07',
    loading: false,
    pageError: null,
    canGoNext: false,
    previousMonth: '2026-06',
    nextMonth: '2026-08',
    selectGroup: vi.fn(),
    setMonth: vi.fn(),
    refresh: vi.fn(),
  }
}

function LocationProbe() {
  return <output aria-label="current search">{useLocation().search}</output>
}

describe('CleaningDailyPage', () => {
  it('starts with a Sunday-first calendar and accessible completion counts', () => {
    useCleaningReport.mockReturnValue(makeState())
    render(<CleaningDailyPage onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper('/cleaning/daily?group=group-1&month=2026-07'),
    })

    expect(screen.getByRole('heading', { name: '掃除の日別完了状況' })).toBeInTheDocument()
    expect(screen.getByRole('grid', { name: '掃除の日別完了カレンダー' })).toBeInTheDocument()
    expect(screen.getByRole('gridcell', { name: '7月1日: 2回完了' })).toBeInTheDocument()
    expect(screen.getByRole('gridcell', { name: '7月2日: 0回完了' })).toBeInTheDocument()
  })

  it('shows the bar chart and stores the selected view in the URL', async () => {
    const user = userEvent.setup()
    useCleaningReport.mockReturnValue(makeState())
    render(
      <>
        <CleaningDailyPage onUnauthorized={vi.fn()} />
        <LocationProbe />
      </>,
      { wrapper: createAppWrapper('/cleaning/daily?group=group-1&month=2026-07') },
    )

    await user.click(screen.getByRole('button', { name: 'グラフ' }))

    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.queryByRole('grid')).not.toBeInTheDocument()
    expect(screen.getByLabelText('current search')).toHaveTextContent('?group=group-1&month=2026-07&view=chart')
  })

  it('opens the chart when view=chart is in the URL', () => {
    useCleaningReport.mockReturnValue(makeState())
    render(<CleaningDailyPage onUnauthorized={vi.fn()} />, {
      wrapper: createAppWrapper('/cleaning/daily?group=group-1&month=2026-07&view=chart'),
    })

    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.queryByRole('grid')).not.toBeInTheDocument()
  })
})
