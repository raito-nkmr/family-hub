import { useEffect, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AddTaskIcon, CategoryIcon, TaskAltIcon, UndoIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { ChoreCategoryManagerDialog } from './components/ChoreCategoryManagerDialog'
import { ChoreTaskCard } from './components/ChoreTaskCard'
import { ChoreTaskFormDialog } from './components/ChoreTaskFormDialog'
import { getChoreDueStatus, getChoreProgress } from './status'
import { useChores } from './useChores'

interface ChoresPageProps {
  onUnauthorized: () => void
}

const ALL_CATEGORIES = 'all'

export function ChoresPage({ onUnauthorized }: ChoresPageProps) {
  const { t } = useTranslation()
  const state = useChores({ onUnauthorized })
  const [now, setNow] = useState(() => new Date())
  const [swipeOpenTaskId, setSwipeOpenTaskId] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState(ALL_CATEGORIES)
  const activeTasks = state.tasks.filter((task) => task.is_active)
  const inactiveTasks = state.tasks.filter((task) => !task.is_active)
  const isAdmin = state.selectedGroup?.current_user_role === 'admin'
  const effectiveSelectedCategory =
    selectedCategory === ALL_CATEGORIES || state.categories.some((category) => category.id === selectedCategory)
      ? selectedCategory
      : ALL_CATEGORIES
  const visibleActiveTasks = activeTasks.filter((task) => matchesCategory(task.category_id, effectiveSelectedCategory))
  const visibleInactiveTasks = inactiveTasks.filter((task) =>
    matchesCategory(task.category_id, effectiveSelectedCategory),
  )
  const selectedCategoryName =
    state.categories.find((category) => category.id === effectiveSelectedCategory)?.name ?? ''

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000)
    return () => window.clearInterval(timer)
  }, [])

  const handleGridPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return
    const card = target.closest<HTMLElement>('[data-chore-task-id]')
    if (card?.dataset.choreTaskId !== swipeOpenTaskId) setSwipeOpenTaskId(null)
  }

  const handleSelectGroup = async (groupId: string) => {
    setSwipeOpenTaskId(null)
    setSelectedCategory('all')
    await state.selectGroup(groupId)
  }

  return (
    <>
      <main id="top" className="chore-page">
        <section className="chore-hero">
          <div>
            <h1>{t('chores.title')}</h1>
            <p>{t('chores.description')}</p>
          </div>
          <div className="chore-hero__actions">
            {isAdmin && (
              <button
                className="primary-button icon-button"
                type="button"
                disabled={state.loading}
                onClick={() => state.openTaskDialog()}
              >
                <AddTaskIcon />
                {t('chores.add')}
              </button>
            )}
          </div>
        </section>

        <section className="chore-board" aria-labelledby="chore-board-heading">
          <GroupScopedToolbar
            groups={state.groups}
            selectedGroupId={state.selectedGroupId}
            selectId="chore-group"
            label={t('chores.group')}
            selectDisabled={
              state.loading || state.submitting || state.pendingTaskIds.size > 0 || state.groups.length === 0
            }
            refreshDisabled={state.loading || state.submitting || state.pendingTaskIds.size > 0}
            onSelectGroup={handleSelectGroup}
            onRefresh={state.refresh}
          />

          {state.selectedGroup && (
            <div className="chore-category-toolbar">
              <nav className="chore-category-filter" aria-label={t('chores.categoryFilter')}>
                <button
                  className={`chore-category-filter__button${effectiveSelectedCategory === ALL_CATEGORIES ? ' chore-category-filter__button--active' : ''}`}
                  type="button"
                  aria-pressed={effectiveSelectedCategory === ALL_CATEGORIES}
                  onClick={() => setSelectedCategory(ALL_CATEGORIES)}
                >
                  {t('chores.allCategories')}
                </button>
                {state.categories.map((category) => (
                  <button
                    className={`chore-category-filter__button${effectiveSelectedCategory === category.id ? ' chore-category-filter__button--active' : ''}`}
                    key={category.id}
                    type="button"
                    aria-pressed={effectiveSelectedCategory === category.id}
                    onClick={() => setSelectedCategory(category.id)}
                  >
                    {category.name}
                  </button>
                ))}
              </nav>
              <button
                className="secondary-button icon-button"
                type="button"
                disabled={state.submitting}
                onClick={state.openCategoryDialog}
              >
                <CategoryIcon />
                {t('chores.categoryManage')}
              </button>
            </div>
          )}

          <div className="section-heading chore-board__heading">
            <div>
              <h2 id="chore-board-heading">{t('chores.board')}</h2>
              <p>
                {visibleActiveTasks.length > 0
                  ? t('chores.count', { count: visibleActiveTasks.length })
                  : t('chores.emptySummary')}
              </p>
            </div>
          </div>

          {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
          {state.loading ? (
            <div className="chore-grid" aria-label={t('chores.loading')}>
              {Array.from({ length: 3 }, (_, index) => (
                <div className="chore-card chore-card--skeleton" key={index} />
              ))}
            </div>
          ) : state.groups.length === 0 ? (
            <EmptyState
              className="chore-empty-state"
              icon={<TaskAltIcon />}
              title={t('chores.groupNeeded')}
              description={t('chores.groupNeededHelp')}
            />
          ) : visibleActiveTasks.length === 0 ? (
            <EmptyState
              className="chore-empty-state"
              icon={<TaskAltIcon />}
              title={
                effectiveSelectedCategory === ALL_CATEGORIES
                  ? t('chores.empty')
                  : t('chores.emptyCategory', { categoryName: selectedCategoryName })
              }
              description={
                state.categories.length === 0
                  ? t('chores.emptyNoCategoriesHelp')
                  : effectiveSelectedCategory === ALL_CATEGORIES
                    ? t(isAdmin ? 'chores.emptyAdmin' : 'chores.emptyMember')
                    : t('chores.emptyCategoryHelp')
              }
            />
          ) : (
            <div className="chore-grid" onPointerDown={handleGridPointerDown}>
              {visibleActiveTasks.map((task) => {
                const due = getChoreDueStatus(task, now)
                const progress = getChoreProgress(task, now)
                const busy = state.pendingTaskIds.has(task.id)
                return (
                  <ChoreTaskCard
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
            <details className="chore-inactive">
              <summary>{t('chores.inactive', { count: visibleInactiveTasks.length })}</summary>
              <div className="chore-inactive__list">
                {visibleInactiveTasks.map((task) => (
                  <div key={task.id}>
                    <span>{task.task_name}</span>
                    <button
                      className="success-button icon-button"
                      type="button"
                      disabled={state.pendingTaskIds.has(task.id)}
                      onClick={() => void state.setTaskActive(task, true)}
                    >
                      <UndoIcon />
                      {t('chores.restart')}
                    </button>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>
      </main>

      {state.showTaskDialog && (
        <ChoreTaskFormDialog
          task={state.editingTask}
          categories={state.categories}
          submitting={state.submitting}
          error={state.dialogError}
          onSubmit={state.saveTask}
          onClose={state.closeTaskDialog}
        />
      )}
      {state.showCategoryDialog && (
        <ChoreCategoryManagerDialog
          categories={state.categories}
          submitting={state.submitting}
          actionId={state.categoryActionId}
          error={state.categoryDialogError}
          onCreate={state.createCategory}
          onRename={state.renameCategory}
          onDelete={state.removeCategory}
          onReorder={state.reorderCategories}
          onClose={state.closeCategoryDialog}
        />
      )}
    </>
  )
}

function matchesCategory(categoryId: string, selectedCategory: string): boolean {
  return selectedCategory === ALL_CATEGORIES || categoryId === selectedCategory
}
