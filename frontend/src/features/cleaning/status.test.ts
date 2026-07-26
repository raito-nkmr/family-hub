import { describe, expect, it } from 'vitest'
import type { CleaningTask } from './api'
import { getCleaningDueStatus } from './status'

function makeTask(overrides: Partial<CleaningTask> = {}): CleaningTask {
  return {
    id: 'task-id',
    group_id: 'group-id',
    name: 'お風呂',
    interval_days: 1,
    is_active: true,
    created_by_user_id: 'user-id',
    created_at: '2026-07-14T00:00:00Z',
    updated_at: '2026-07-14T00:00:00Z',
    next_due_at: '2026-07-16T00:00:00Z',
    current_user_role: 'admin',
    last_completion: null,
    ...overrides,
  }
}

describe('getCleaningDueStatus', () => {
  const now = new Date('2026-07-15T00:00:00Z')

  it('marks a task due within 24 hours', () => {
    expect(getCleaningDueStatus(makeTask(), now)).toEqual({ state: 'due-soon', label: '24時間以内' })
  })

  it('marks an overdue task', () => {
    const task = makeTask({ next_due_at: '2026-07-13T00:00:00Z' })

    expect(getCleaningDueStatus(task, now)).toEqual({ state: 'overdue', label: '2日超過' })
  })

  it('marks an inactive task independently of its due date', () => {
    expect(getCleaningDueStatus(makeTask({ is_active: false }), now)).toEqual({
      state: 'inactive',
      label: '停止中',
    })
  })
})
