import { useRef, type TouchEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../../shared/lib/format'
import { CancelIcon, CheckCircleIcon, EditIcon } from '../../../shared/ui/icons'
import type { CleaningTask } from '../api'
import type { CleaningDueStatus, CleaningProgress } from '../status'

const SWIPE_THRESHOLD_PX = 64

interface CleaningTaskCardProps {
  task: CleaningTask
  due: CleaningDueStatus
  progress: CleaningProgress
  isAdmin: boolean
  busy: boolean
  swipeOpen: boolean
  onSwipeOpen: () => void
  onSwipeClose: () => void
  onComplete: () => void
  onEdit: () => void
  onPause: () => void
}

export function CleaningTaskCard({
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
}: CleaningTaskCardProps) {
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
      className={`cleaning-card-swipe${swipeOpen ? ' cleaning-card-swipe--open' : ''}`}
      data-cleaning-task-id={task.id}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={() => {
        swipeStartRef.current = null
      }}
    >
      <div className="cleaning-card__swipe-action" aria-hidden={!swipeOpen}>
        <button
          className="cleaning-card__swipe-complete"
          type="button"
          tabIndex={swipeOpen ? 0 : -1}
          disabled={busy}
          onClick={onComplete}
        >
          <CheckCircleIcon />
          {t(busy ? 'cleaning.recording' : 'cleaning.complete')}
        </button>
      </div>

      <article
        className={`cleaning-card cleaning-card--${due.state}`}
        onClick={() => {
          if (swipeOpen) onSwipeClose()
        }}
      >
        <div className="cleaning-card__heading">
          <h3>{task.name}</h3>
          {isAdmin && (
            <div className="cleaning-card__actions">
              <button
                className="cleaning-card__edit"
                type="button"
                aria-label={t('cleaning.editLabel', { name: task.name })}
                disabled={busy}
                onClick={onEdit}
              >
                <EditIcon />
              </button>
              <button
                className="danger-button icon-button cleaning-card__stop"
                type="button"
                aria-label={t('cleaning.stop', { name: task.name })}
                title={t('cleaning.stop', { name: task.name })}
                disabled={busy}
                onClick={onPause}
              >
                <CancelIcon />
              </button>
            </div>
          )}
        </div>

        <div className={`cleaning-card__progress cleaning-card__progress--${progress.state}`}>
          <div className="cleaning-card__progress-labels">
            <span>{t('cleaning.progressElapsed', { elapsed: progress.elapsedDays, total: task.interval_days })}</span>
            {progress.state !== 'scheduled' && (
              <span className={`cleaning-card__status cleaning-card__status--${due.state}`}>{due.label}</span>
            )}
          </div>
          <div
            className="cleaning-card__progress-track"
            role="progressbar"
            aria-label={t('cleaning.progressLabel', { name: task.name })}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress.percent}
            aria-valuetext={t('cleaning.progressAria', {
              elapsed: progress.elapsedDays,
              total: task.interval_days,
              remaining: progress.remainingDays,
              status: due.label,
            })}
          >
            <span className="cleaning-card__progress-fill" style={{ width: `${progress.percent}%` }} />
          </div>
        </div>

        <p className="cleaning-card__history">
          {task.last_completion
            ? t('cleaning.lastCompletedMeta', {
                date: formatDateTime(task.last_completion.completed_at),
                username: task.last_completion.completed_by_username,
              })
            : t('cleaning.never')}
        </p>

        <button
          className="cleaning-card__complete cleaning-card__complete--desktop"
          type="button"
          disabled={busy}
          onClick={onComplete}
        >
          <CheckCircleIcon />
          {t(busy ? 'cleaning.recording' : 'cleaning.complete')}
        </button>
      </article>
    </div>
  )
}
