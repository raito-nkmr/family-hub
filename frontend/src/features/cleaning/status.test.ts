import { describe, expect, it } from 'vitest'
import type { CleaningTask } from './api'
import { getCleaningDueStatus, getCleaningProgress } from './status'

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

describe('getCleaningProgress', () => {
  const now = new Date('2026-07-15T00:00:00Z')

  it('reports elapsed time and a healthy color state', () => {
    const task = makeTask({
      interval_days: 5,
      created_at: '2026-07-10T00:00:00Z',
      next_due_at: '2026-07-15T00:00:00Z',
    })

    expect(getCleaningProgress(task, new Date('2026-07-12T00:00:00Z'))).toEqual({
      state: 'scheduled',
      percent: 40,
      elapsedDays: 2,
      remainingDays: 3,
    })
  })

  it('switches to the warning state when 20 percent remains', () => {
    const task = makeTask({
      interval_days: 5,
      created_at: '2026-07-10T00:00:00Z',
      next_due_at: '2026-07-15T00:00:00Z',
    })

    expect(getCleaningProgress(task, new Date('2026-07-14T00:00:00Z'))).toMatchObject({
      state: 'due-soon',
      percent: 80,
      elapsedDays: 4,
      remainingDays: 1,
    })
  })

  it('uses the overdue state at the deadline and clamps later progress to 100 percent', () => {
    const task = makeTask({
      interval_days: 5,
      created_at: '2026-07-10T00:00:00Z',
      next_due_at: '2026-07-15T00:00:00Z',
    })

    expect(getCleaningProgress(task, new Date('2026-07-15T00:00:00Z'))).toMatchObject({
      state: 'overdue',
      percent: 100,
      elapsedDays: 5,
      remainingDays: 0,
    })
    expect(getCleaningProgress(task, new Date('2026-07-16T00:00:00Z'))).toMatchObject({
      state: 'overdue',
      percent: 100,
      elapsedDays: 5,
      remainingDays: 0,
    })
  })

  it('returns a neutral state for inactive tasks', () => {
    expect(getCleaningProgress(makeTask({ is_active: false }), now)).toEqual({
      state: 'inactive',
      percent: 0,
      elapsedDays: 0,
      remainingDays: 1,
    })
  })
})
