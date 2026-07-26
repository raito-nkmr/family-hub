import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CleaningPage } from './CleaningPage'
import type { CleaningTask } from './api'

const complete = vi.fn()
const useCleaning = vi.fn()

vi.mock('./useCleaning', () => ({
  useCleaning: () => useCleaning(),
}))

function makeTask(): CleaningTask {
  return {
    id: 'task-id',
    group_id: 'group-id',
    name: 'お風呂',
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
      tasks: [makeTask()],
      loading: false,
      submitting: false,
      pendingTaskIds: new Set<string>(),
      editingTask: null,
      showTaskDialog: false,
      pageError: null,
      dialogError: null,
      selectGroup: vi.fn(),
      saveTask: vi.fn(),
      complete,
      setTaskActive: vi.fn(),
      refresh: vi.fn(),
      openTaskDialog: vi.fn(),
      closeTaskDialog: vi.fn(),
    })
  })

  it('shows the shared task and records completion', async () => {
    const user = userEvent.setup()
    render(<CleaningPage onUnauthorized={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'お風呂' })).toBeInTheDocument()
    expect(screen.getByText('family-member')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '掃除完了' }))

    expect(complete).toHaveBeenCalledWith(expect.objectContaining({ id: 'task-id' }))
  })
})
