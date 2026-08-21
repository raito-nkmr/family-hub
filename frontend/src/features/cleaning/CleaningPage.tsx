import { useEffect, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AddTaskIcon, CleaningIcon, UndoIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { CleaningTaskCard } from './components/CleaningTaskCard'
import { CleaningTaskFormDialog } from './components/CleaningTaskFormDialog'
import type { CleaningTaskCategory } from './api'
import { getCleaningDueStatus, getCleaningProgress } from './status'
import { useCleaning } from './useCleaning'

interface CleaningPageProps {
  onUnauthorized: () => void
}

const CATEGORY_FILTERS = ['all', 'watering', 'cleaning', 'children'] as const
type CategoryFilter = (typeof CATEGORY_FILTERS)[number]

export function CleaningPage({ onUnauthorized }: CleaningPageProps) {
  const { t } = useTranslation()
  const state = useCleaning({ onUnauthorized })
  const [now, setNow] = useState(() => new Date())
  const [swipeOpenTaskId, setSwipeOpenTaskId] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<CategoryFilter>('all')
  const activeTasks = state.tasks.filter((task) => task.is_active)
  const inactiveTasks = state.tasks.filter((task) => !task.is_active)
  const isAdmin = state.selectedGroup?.current_user_role === 'admin'
  const visibleActiveTasks = activeTasks.filter((task) => matchesCategory(task.category, selectedCategory))
  const visibleInactiveTasks = inactiveTasks.filter((task) => matchesCategory(task.category, selectedCategory))

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])

  const handleGridPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return
    const card = target.closest<HTMLElement>('[data-cleaning-task-id]')
    if (card?.dataset.cleaningTaskId !== swipeOpenTaskId) setSwipeOpenTaskId(null)
  }

  const handleSelectGroup = async (groupId: string) => {
    setSwipeOpenTaskId(null)
    setSelectedCategory('all')
    await state.selectGroup(groupId)
  }

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
          <GroupScopedToolbar
            groups={state.groups}
            selectedGroupId={state.selectedGroupId}
            selectId="cleaning-group"
            label={t('cleaning.group')}
            selectDisabled={
              state.loading || state.submitting || state.pendingTaskIds.size > 0 || state.groups.length === 0
            }
            refreshDisabled={state.loading || state.submitting || state.pendingTaskIds.size > 0}
            onSelectGroup={handleSelectGroup}
            onRefresh={state.refresh}
          />

          {state.groups.length > 0 && (
            <nav className="cleaning-category-filter" aria-label={t('cleaning.categoryFilter')}>
              {CATEGORY_FILTERS.map((category) => (
                <button
                  className={`cleaning-category-filter__button${selectedCategory === category ? ' cleaning-category-filter__button--active' : ''}`}
                  key={category}
                  type="button"
                  aria-pressed={selectedCategory === category}
                  onClick={() => setSelectedCategory(category)}
                >
                  {t(`cleaning.categories.${category}`)}
                </button>
              ))}
            </nav>
          )}

          <div className="section-heading cleaning-board__heading">
            <div>
              <h2 id="cleaning-board-heading">{t('cleaning.board')}</h2>
              <p>
                {visibleActiveTasks.length > 0
                  ? t('cleaning.count', { count: visibleActiveTasks.length })
                  : t('cleaning.emptySummary')}
              </p>
            </div>
          </div>

          {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
          {state.loading ? (
            <div className="cleaning-grid" aria-label={t('cleaning.loading')}>
              {Array.from({ length: 3 }, (_, index) => (
                <div className="cleaning-card cleaning-card--skeleton" key={index} />
              ))}
            </div>
          ) : state.groups.length === 0 ? (
            <EmptyState
              className="cleaning-empty-state"
              icon={<CleaningIcon />}
              title={t('cleaning.groupNeeded')}
              description={t('cleaning.groupNeededHelp')}
            />
          ) : visibleActiveTasks.length === 0 ? (
            <EmptyState
              className="cleaning-empty-state"
              icon={<CleaningIcon />}
              title={
                selectedCategory === 'all'
                  ? t('cleaning.empty')
                  : t('cleaning.emptyCategory', { category: t(`cleaning.categories.${selectedCategory}`) })
              }
              description={
                selectedCategory === 'all'
                  ? t(isAdmin ? 'cleaning.emptyAdmin' : 'cleaning.emptyMember')
                  : t('cleaning.emptyCategoryHelp')
              }
            />
          ) : (
            <div className="cleaning-grid" onPointerDown={handleGridPointerDown}>
              {visibleActiveTasks.map((task) => {
                const due = getCleaningDueStatus(task, now)
                const progress = getCleaningProgress(task, now)
                const busy = state.pendingTaskIds.has(task.id)
                return (
                  <CleaningTaskCard
                    key={task.id}
                    task={task}
                    due={due}
                    progress={progress}
                    isAdmin={isAdmin}
                    busy={busy}
                    swipeOpen={swipeOpenTaskId === task.id}
                    onSwipeOpen={() => setSwipeOpenTaskId(task.id)}
                    onSwipeClose={() => setSwipeOpenTaskId(null)}
                    onComplete={() => {
                      setSwipeOpenTaskId(null)
                      void state.complete(task)
                    }}
                    onEdit={() => state.openTaskDialog(task)}
                    onPause={() => void state.setTaskActive(task, false)}
                  />
                )
              })}
            </div>
          )}

          {isAdmin && visibleInactiveTasks.length > 0 && (
            <details className="cleaning-inactive">
              <summary>{t('cleaning.inactive', { count: visibleInactiveTasks.length })}</summary>
              <div className="cleaning-inactive__list">
                {visibleInactiveTasks.map((task) => (
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

function matchesCategory(category: CleaningTaskCategory, selectedCategory: CategoryFilter): boolean {
  return selectedCategory === 'all' || category === selectedCategory
}
