import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../shared/lib/format'
import {
  AddTaskIcon,
  CancelIcon,
  CheckCircleIcon,
  CleaningIcon,
  EditIcon,
  RefreshIcon,
  UndoIcon,
} from '../../shared/ui/icons'
import { CleaningTaskFormDialog } from './components/CleaningTaskFormDialog'
import { getCleaningDueStatus } from './status'
import { useCleaning } from './useCleaning'

interface CleaningPageProps {
  onUnauthorized: () => void
}

export function CleaningPage({ onUnauthorized }: CleaningPageProps) {
  const { t } = useTranslation()
  const state = useCleaning({ onUnauthorized })
  const activeTasks = state.tasks.filter((task) => task.is_active)
  const inactiveTasks = state.tasks.filter((task) => !task.is_active)
  const isAdmin = state.selectedGroup?.current_user_role === 'admin'

  return (
    <>
      <main id="top" className="cleaning-page">
        <section className="cleaning-hero">
          <div>
            <h1>{t('cleaning.title')}</h1>
            <p>{t('cleaning.description')}</p>
          </div>
          {isAdmin && (
            <button
              className="primary-button icon-button"
              type="button"
              disabled={state.loading}
              onClick={() => state.openTaskDialog()}
            >
              <AddTaskIcon />
              {t('cleaning.add')}
            </button>
          )}
        </section>

        <section className="cleaning-board" aria-labelledby="cleaning-board-heading">
          <div className="cleaning-board__toolbar">
            <div>
              <label htmlFor="cleaning-group">{t('cleaning.group')}</label>
              <select
                id="cleaning-group"
                value={state.selectedGroupId ?? ''}
                disabled={
                  state.loading || state.submitting || state.pendingTaskIds.size > 0 || state.groups.length === 0
                }
                onChange={(event) => void state.selectGroup(event.target.value)}
              >
                {state.groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="refresh-button"
              type="button"
              disabled={state.loading || state.submitting || state.pendingTaskIds.size > 0}
              onClick={() => void state.refresh()}
            >
              <RefreshIcon />
              <span>{t('common.refresh')}</span>
            </button>
          </div>

          <div className="section-heading cleaning-board__heading">
            <div>
              <h2 id="cleaning-board-heading">{t('cleaning.board')}</h2>
              <p>
                {activeTasks.length > 0
                  ? t('cleaning.count', { count: activeTasks.length })
                  : t('cleaning.emptySummary')}
              </p>
            </div>
          </div>

          {state.pageError && (
            <div className="page-message page-message--error" role="alert">
              {state.pageError}
            </div>
          )}
          {state.loading ? (
            <div className="cleaning-grid" aria-label={t('cleaning.loading')}>
              {Array.from({ length: 3 }, (_, index) => (
                <div className="cleaning-card cleaning-card--skeleton" key={index} />
              ))}
            </div>
          ) : state.groups.length === 0 ? (
            <div className="empty-state cleaning-empty-state">
              <span>
                <CleaningIcon />
              </span>
              <h3>{t('cleaning.groupNeeded')}</h3>
              <p>{t('cleaning.groupNeededHelp')}</p>
            </div>
          ) : activeTasks.length === 0 ? (
            <div className="empty-state cleaning-empty-state">
              <span>
                <CleaningIcon />
              </span>
              <h3>{t('cleaning.empty')}</h3>
              <p>{t(isAdmin ? 'cleaning.emptyAdmin' : 'cleaning.emptyMember')}</p>
            </div>
          ) : (
            <div className="cleaning-grid">
              {activeTasks.map((task) => {
                const due = getCleaningDueStatus(task)
                const busy = state.pendingTaskIds.has(task.id)
                return (
                  <article className={`cleaning-card cleaning-card--${due.state}`} key={task.id}>
                    <div className="cleaning-card__heading">
                      <span className={`cleaning-card__status cleaning-card__status--${due.state}`}>{due.label}</span>
                      {isAdmin && (
                        <button
                          className="cleaning-card__edit"
                          type="button"
                          aria-label={t('cleaning.editLabel', { name: task.name })}
                          disabled={busy}
                          onClick={() => state.openTaskDialog(task)}
                        >
                          <EditIcon />
                        </button>
                      )}
                    </div>
                    <div className="cleaning-card__body">
                      <h3>{task.name}</h3>
                      <p>
                        {task.interval_days === 1
                          ? t('cleaning.everyDay')
                          : t('cleaning.everyDays', { count: task.interval_days })}
                      </p>
                    </div>
                    <dl className="cleaning-card__history">
                      <div>
                        <dt>{t('cleaning.previous')}</dt>
                        <dd>
                          {task.last_completion
                            ? formatDateTime(task.last_completion.completed_at)
                            : t('cleaning.never')}
                        </dd>
                      </div>
                      {task.last_completion && (
                        <div>
                          <dt>{t('cleaning.completedBy')}</dt>
                          <dd>{task.last_completion.completed_by_username}</dd>
                        </div>
                      )}
                      <div>
                        <dt>{t('cleaning.nextDue')}</dt>
                        <dd>{formatDateTime(task.next_due_at)}</dd>
                      </div>
                    </dl>
                    <button
                      className="cleaning-card__complete"
                      type="button"
                      disabled={busy}
                      onClick={() => void state.complete(task)}
                    >
                      <CheckCircleIcon />
                      {t(busy ? 'cleaning.recording' : 'cleaning.complete')}
                    </button>
                    {isAdmin && (
                      <button
                        className="danger-button icon-button cleaning-card__stop"
                        type="button"
                        disabled={busy}
                        onClick={() => void state.setTaskActive(task, false)}
                      >
                        <CancelIcon />
                        {t('cleaning.stop')}
                      </button>
                    )}
                  </article>
                )
              })}
            </div>
          )}

          {isAdmin && inactiveTasks.length > 0 && (
            <details className="cleaning-inactive">
              <summary>{t('cleaning.inactive', { count: inactiveTasks.length })}</summary>
              <div className="cleaning-inactive__list">
                {inactiveTasks.map((task) => (
                  <div key={task.id}>
                    <span>{task.name}</span>
                    <button
                      className="success-button icon-button"
                      type="button"
                      disabled={state.pendingTaskIds.has(task.id)}
                      onClick={() => void state.setTaskActive(task, true)}
                    >
                      <UndoIcon />
                      {t('cleaning.restart')}
                    </button>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>
      </main>

      {state.showTaskDialog && (
        <CleaningTaskFormDialog
          task={state.editingTask}
          submitting={state.submitting}
          error={state.dialogError}
          onSubmit={state.saveTask}
          onClose={state.closeTaskDialog}
        />
      )}
    </>
  )
}
