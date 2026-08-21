import i18n from '../../i18n'
import type { ChoreTask } from './api'

const DAY_MILLISECONDS = 24 * 60 * 60 * 1000

export type ChoreDueState = 'overdue' | 'due-soon' | 'scheduled' | 'inactive'

export interface ChoreDueStatus {
  state: ChoreDueState
  label: string
}

export interface ChoreProgress {
  state: ChoreDueState
  percent: number
  elapsedDays: number
  remainingDays: number
}

export function getChoreProgress(task: ChoreTask, now = new Date()): ChoreProgress {
  if (!task.is_active) {
    return {
      state: 'inactive',
      percent: 0,
      elapsedDays: 0,
      remainingDays: task.interval_days,
    }
  }

  const baseline = task.last_completion?.completed_at ?? task.created_at
  const elapsedMilliseconds = Math.max(0, now.getTime() - new Date(baseline).getTime())
  const intervalMilliseconds = task.interval_days * DAY_MILLISECONDS
  const millisecondsUntilDue = new Date(task.next_due_at).getTime() - now.getTime()
  const percent = Math.min(100, Math.max(0, Math.round((elapsedMilliseconds / intervalMilliseconds) * 100)))
  const elapsedDays = Math.min(task.interval_days, Math.floor(elapsedMilliseconds / DAY_MILLISECONDS))
  const remainingDays = Math.max(0, Math.ceil(millisecondsUntilDue / DAY_MILLISECONDS))

  if (millisecondsUntilDue <= 0) {
    return { state: 'overdue', percent, elapsedDays, remainingDays }
  }

  if (millisecondsUntilDue / intervalMilliseconds <= 0.2) {
    return { state: 'due-soon', percent, elapsedDays, remainingDays }
  }

  return { state: 'scheduled', percent, elapsedDays, remainingDays }
}

export function getChoreDueStatus(task: ChoreTask, now = new Date()): ChoreDueStatus {
  if (!task.is_active) return { state: 'inactive', label: i18n.t('chores.statusInactive') }
  const millisecondsUntilDue = new Date(task.next_due_at).getTime() - now.getTime()
  if (millisecondsUntilDue <= 0) {
    const overdueDays = Math.max(1, Math.ceil(Math.abs(millisecondsUntilDue) / DAY_MILLISECONDS))
    return {
      state: 'overdue',
      label: i18n.t(overdueDays === 1 ? 'chores.overdue' : 'chores.overdueDays', { count: overdueDays }),
    }
  }
  const remainingDays = Math.ceil(millisecondsUntilDue / DAY_MILLISECONDS)
  if (remainingDays <= 1) return { state: 'due-soon', label: i18n.t('chores.dueSoon') }
  return { state: 'scheduled', label: i18n.t('chores.remaining', { count: remainingDays }) }
}
