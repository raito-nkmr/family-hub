import { useRef, type TouchEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../../shared/lib/format'
import { CancelIcon, CheckCircleIcon, EditIcon } from '../../../shared/ui/icons'
import type { ChoreTask } from '../api'
import type { ChoreDueStatus, ChoreProgress } from '../status'

const SWIPE_THRESHOLD_PX = 64

interface ChoreTaskCardProps {
  task: ChoreTask
  due: ChoreDueStatus
  progress: ChoreProgress
  isAdmin: boolean
  busy: boolean
  swipeOpen: boolean
  onSwipeOpen: () => void
  onSwipeClose: () => void
  onComplete: () => void
  onEdit: () => void
  onPause: () => void
}

export function ChoreTaskCard({
  task,
  due,
  progress,
  isAdmin,
  busy,
  swipeOpen,
  onSwipeOpen,
  onSwipeClose,
  onComplete,
  onEdit,
  onPause,
}: ChoreTaskCardProps) {
  const { t } = useTranslation()
  const swipeStartRef = useRef<{ x: number; y: number } | null>(null)

  const handleTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    if (event.touches.length !== 1 || busy) {
      swipeStartRef.current = null
      return
    }
    const touch = event.touches[0]
    swipeStartRef.current = { x: touch.clientX, y: touch.clientY }
  }

  const handleTouchEnd = (event: TouchEvent<HTMLDivElement>) => {
    const start = swipeStartRef.current
    swipeStartRef.current = null
    if (!start || busy || event.changedTouches.length !== 1) return

    const touch = event.changedTouches[0]
    const deltaX = touch.clientX - start.x
    const deltaY = touch.clientY - start.y
    if (deltaX < SWIPE_THRESHOLD_PX || deltaX <= Math.abs(deltaY)) return
    onSwipeOpen()
  }

  return (
    <div
      className={`chore-card-swipe${swipeOpen ? ' chore-card-swipe--open' : ''}`}
      data-chore-task-id={task.id}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={() => {
        swipeStartRef.current = null
      }}
    >
      <div className="chore-card__swipe-action" aria-hidden={!swipeOpen}>
        <button
          className="chore-card__swipe-complete"
          type="button"
          tabIndex={swipeOpen ? 0 : -1}
          disabled={busy}
          onClick={onComplete}
        >
          <CheckCircleIcon />
          {t(busy ? 'chores.recording' : 'chores.complete')}
        </button>
      </div>

      <article
        className={`chore-card chore-card--${due.state}`}
        onClick={() => {
          if (swipeOpen) onSwipeClose()
        }}
      >
        <div className="chore-card__heading">
          <h3>{task.task_name}</h3>
          {isAdmin && (
            <div className="chore-card__actions">
              <button
                className="chore-card__edit"
                type="button"
                aria-label={t('chores.editLabel', { taskName: task.task_name })}
                disabled={busy}
                onClick={onEdit}
              >
                <EditIcon />
              </button>
              <button
                className="danger-button icon-button chore-card__stop"
                type="button"
                aria-label={t('chores.pause', { taskName: task.task_name })}
                title={t('chores.pause', { taskName: task.task_name })}
                disabled={busy}
                onClick={onPause}
              >
                <CancelIcon />
              </button>
            </div>
          )}
        </div>

        <div className={`chore-card__progress chore-card__progress--${progress.state}`}>
          <div className="chore-card__progress-labels">
            <span>{t('chores.progressElapsed', { elapsed: progress.elapsedDays, total: task.interval_days })}</span>
            {progress.state !== 'scheduled' && (
              <span className={`chore-card__status chore-card__status--${due.state}`}>{due.label}</span>
            )}
          </div>
          <div
            className="chore-card__progress-track"
            role="progressbar"
            aria-label={t('chores.progressLabel', { taskName: task.task_name })}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress.percent}
            aria-valuetext={t('chores.progressAria', {
              elapsed: progress.elapsedDays,
              total: task.interval_days,
              remaining: progress.remainingDays,
              status: due.label,
            })}
          >
            <span className="chore-card__progress-fill" style={{ width: `${progress.percent}%` }} />
          </div>
        </div>

        <p className="chore-card__history">
          {task.last_completion
            ? t('chores.lastCompletedMeta', {
                date: formatDateTime(task.last_completion.completed_at),
                username: task.last_completion.completed_by_username,
              })
            : t('chores.never')}
        </p>

        <button
          className="chore-card__complete chore-card__complete--desktop"
          type="button"
          disabled={busy}
          onClick={onComplete}
        >
          <CheckCircleIcon />
          {t(busy ? 'chores.recording' : 'chores.complete')}
        </button>
      </article>
    </div>
  )
}
