import i18n from '../../i18n'
import type { CleaningTask } from './api'

const DAY_MILLISECONDS = 24 * 60 * 60 * 1000

export type CleaningDueState = 'overdue' | 'due-soon' | 'scheduled' | 'inactive'

export interface CleaningDueStatus {
  state: CleaningDueState
  label: string
}

export function getCleaningDueStatus(task: CleaningTask, now = new Date()): CleaningDueStatus {
  if (!task.is_active) return { state: 'inactive', label: i18n.t('cleaning.statusInactive') }
  const millisecondsUntilDue = new Date(task.next_due_at).getTime() - now.getTime()
  if (millisecondsUntilDue <= 0) {
    const overdueDays = Math.max(1, Math.ceil(Math.abs(millisecondsUntilDue) / DAY_MILLISECONDS))
    return {
      state: 'overdue',
      label: i18n.t(overdueDays === 1 ? 'cleaning.overdue' : 'cleaning.overdueDays', { count: overdueDays }),
    }
  }
  const remainingDays = Math.ceil(millisecondsUntilDue / DAY_MILLISECONDS)
  if (remainingDays <= 1) return { state: 'due-soon', label: i18n.t('cleaning.dueSoon') }
  return { state: 'scheduled', label: i18n.t('cleaning.remaining', { count: remainingDays }) }
}
