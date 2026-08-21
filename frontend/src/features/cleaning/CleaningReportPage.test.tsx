import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { CleaningReportPage } from './CleaningReportPage'

const useCleaningReport = vi.fn()

vi.mock('./useCleaningReport', () => ({
  useCleaningReport: () => useCleaningReport(),
}))

const report = {
  group_id: 'group-1',
  month: '2026-07',
  timezone: 'Asia/Tokyo',
  summary: { completion_count: 4, unique_task_count: 2, participant_count: 2, category_count: 1 },
  daily: [{ day: '2026-07-01', completion_count: 2, unique_task_count: 1 }],
  categories: [{ category_id: 'category-1', name: '掃除', completion_count: 4, unique_task_count: 2 }],
  members: [
    { user_id: 'user-1', username: '太郎', completion_count: 3, unique_task_count: 2, completion_ratio: 0.75 },
    { user_id: 'user-2', username: '花子', completion_count: 1, unique_task_count: 1, completion_ratio: 0.25 },
  ],
  tasks: [
    {
      task_id: 'task-1',
      name: 'お風呂',
      category_id: 'category-1',
      category_name: '掃除',
      completion_count: 3,
      participant_count: 2,
      members: [{ user_id: 'user-1', username: '太郎', completion_count: 2 }],
    },
  ],
}

describe('CleaningReportPage', () => {
  const makeState = (currentReport = report) => ({
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
    report: currentReport,
    month: '2026-07',
    loading: false,
    pageError: null,
    canGoNext: false,
    previousMonth: '2026-06',
    nextMonth: '2026-08',
    selectGroup: vi.fn(),
    setMonth: vi.fn(),
    refresh: vi.fn(),
  })

  beforeEach(() => {
    vi.clearAllMocks()
    useCleaningReport.mockReturnValue(makeState())
  })

  it('shows the monthly summary, category breakdown, ranking, and task breakdown', () => {
    render(<CleaningReportPage onUnauthorized={vi.fn()} />, { wrapper: createAppWrapper('/cleaning/reports') })

    expect(screen.getByRole('heading', { name: '掃除の月次レポート' })).toBeInTheDocument()
    expect(screen.getAllByText('完了回数').length).toBeGreaterThan(0)
    expect(screen.queryByRole('heading', { name: '日別の完了回数' })).not.toBeInTheDocument()
    expect(screen.getByText('ユーザー別ランキング')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'ユーザー別ランキング' })).toBeInTheDocument()
    expect(screen.getByText('1. 太郎')).toBeInTheDocument()
    expect(screen.getByText('掃除箇所別の実績')).toBeInTheDocument()
    expect(screen.getAllByText('お風呂').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: '掃除一覧へ戻る' })).toHaveAttribute('href', '/cleaning')
  })

  it('moves to the previous month and keeps task details collapsible', async () => {
    const user = userEvent.setup()
    render(<CleaningReportPage onUnauthorized={vi.fn()} />, { wrapper: createAppWrapper('/cleaning/reports') })

    await user.click(screen.getByRole('button', { name: '前月' }))

    expect(useCleaningReport.mock.results[0].value.setMonth).toHaveBeenCalledWith('2026-06')
    expect(screen.getAllByText('お風呂').some((element) => element.closest('details') !== null)).toBe(true)
  })

  it('shows the empty state when a month has no completions', () => {
    useCleaningReport.mockReturnValueOnce(makeState({ ...report, summary: { ...report.summary, completion_count: 0 } }))
    render(<CleaningReportPage onUnauthorized={vi.fn()} />, { wrapper: createAppWrapper('/cleaning/reports') })

    expect(screen.getByText('この月の掃除記録はありません')).toBeInTheDocument()
  })
})
