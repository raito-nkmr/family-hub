import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CleaningPage } from './CleaningPage'
import type { CleaningTask } from './api'

const complete = vi.fn()
const useCleaning = vi.fn()

vi.mock('./useCleaning', () => ({
  useCleaning: () => useCleaning(),
}))

function makeTask(overrides: Partial<CleaningTask> = {}): CleaningTask {
  return {
    id: 'task-id',
    group_id: 'group-id',
    name: 'お風呂',
    category_id: 'cleaning-id',
    interval_days: 1,
    is_active: true,
    created_by_user_id: 'user-id',
    created_at: '2026-07-14T00:00:00Z',
    updated_at: '2026-07-14T00:00:00Z',
    next_due_at: '2099-07-16T00:00:00Z',
    current_user_role: 'admin',
    last_completion: {
      id: 'completion-id',
      completed_by_user_id: 'user-id',
      completed_by_username: 'family-member',
      completed_at: '2026-07-15T00:00:00Z',
    },
    ...overrides,
  }
}

describe('CleaningPage', () => {
  beforeEach(() => {
    complete.mockReset()
    useCleaning.mockReturnValue({
      groups: [
        {
          id: 'group-id',
          name: '同居家族',
          created_by_user_id: 'user-id',
          created_at: '2026-07-14T00:00:00Z',
          updated_at: '2026-07-14T00:00:00Z',
          current_user_role: 'admin',
          member_count: 2,
        },
      ],
      selectedGroupId: 'group-id',
      selectedGroup: { id: 'group-id', current_user_role: 'admin' },
      categories: [
        { id: 'cleaning-id', group_id: 'group-id', name: '掃除', sort_order: 0, created_at: '', updated_at: '' },
        { id: 'watering-id', group_id: 'group-id', name: '水やり', sort_order: 1, created_at: '', updated_at: '' },
      ],
      tasks: [makeTask(), makeTask({ id: 'watering-task-id', name: '花', category_id: 'watering-id' })],
      loading: false,
      submitting: false,
      pendingTaskIds: new Set<string>(),
      editingTask: null,
      showTaskDialog: false,
      showCategoryDialog: false,
      pageError: null,
      dialogError: null,
      categoryDialogError: null,
      categoryActionId: null,
      selectGroup: vi.fn(),
      saveTask: vi.fn(),
      complete,
      setTaskActive: vi.fn(),
      refresh: vi.fn(),
      openTaskDialog: vi.fn(),
      closeTaskDialog: vi.fn(),
      openCategoryDialog: vi.fn(),
      closeCategoryDialog: vi.fn(),
      createCategory: vi.fn(),
      renameCategory: vi.fn(),
      removeCategory: vi.fn(),
      reorderCategories: vi.fn(),
    })
  })

  it('shows the shared task and records completion', async () => {
    const user = userEvent.setup()
    render(<CleaningPage onUnauthorized={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'お風呂' })).toBeInTheDocument()
    expect(screen.getAllByText(/family-member/)).toHaveLength(2)

    const card = screen.getByRole('heading', { name: 'お風呂' }).closest('article')
    expect(card).not.toBeNull()
    await user.click(within(card!).getByRole('button', { name: '掃除完了' }))

    expect(complete).toHaveBeenCalledWith(expect.objectContaining({ id: 'task-id' }))
  })

  it('reveals completion after a right swipe and waits for the action tap', async () => {
    const user = userEvent.setup()
    const { container } = render(<CleaningPage onUnauthorized={vi.fn()} />)
    const card = container.querySelector('.cleaning-card-swipe')
    const swipeAction = container.querySelector('.cleaning-card__swipe-complete')

    expect(card).not.toBeNull()
    expect(swipeAction).not.toBeNull()
    fireEvent.touchStart(card!, { touches: [{ clientX: 100, clientY: 100 }] })
    fireEvent.touchEnd(card!, { changedTouches: [{ clientX: 180, clientY: 100 }] })

    expect(card).toHaveClass('cleaning-card-swipe--open')
    expect(complete).not.toHaveBeenCalled()

    await user.click(swipeAction!)

    expect(complete).toHaveBeenCalledWith(expect.objectContaining({ id: 'task-id' }))
  })

  it('does not open for a left swipe or vertical movement', () => {
    const { container } = render(<CleaningPage onUnauthorized={vi.fn()} />)
    const card = container.querySelector('.cleaning-card-swipe')

    expect(card).not.toBeNull()
    fireEvent.touchStart(card!, { touches: [{ clientX: 100, clientY: 100 }] })
    fireEvent.touchEnd(card!, { changedTouches: [{ clientX: 20, clientY: 100 }] })
    expect(card).not.toHaveClass('cleaning-card-swipe--open')

    fireEvent.touchStart(card!, { touches: [{ clientX: 100, clientY: 100 }] })
    fireEvent.touchEnd(card!, { changedTouches: [{ clientX: 180, clientY: 180 }] })
    expect(card).not.toHaveClass('cleaning-card-swipe--open')
  })

  it('renders an accessible progressbar and compact completion metadata', () => {
    render(<CleaningPage onUnauthorized={vi.fn()} />)

    expect(screen.getByRole('progressbar', { name: 'お風呂の掃除の進捗' })).toHaveAttribute('aria-valuemin', '0')
    expect(screen.getByRole('progressbar', { name: 'お風呂の掃除の進捗' })).toHaveAttribute('aria-valuemax', '100')
    expect(screen.getAllByText(/前回: .*family-member/)).toHaveLength(2)
  })

  it('filters tasks by category', async () => {
    const user = userEvent.setup()
    render(<CleaningPage onUnauthorized={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /^水やり$/ }))

    expect(screen.getByRole('heading', { name: '花' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'お風呂' })).not.toBeInTheDocument()
  })
})
