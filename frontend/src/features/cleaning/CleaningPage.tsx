import { useEffect, useState, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { appPaths } from '../../app/routes'
import { AddTaskIcon, CategoryIcon, TaskAltIcon, UndoIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { CleaningCategoryManagerDialog } from './components/CleaningCategoryManagerDialog'
import { CleaningTaskCard } from './components/CleaningTaskCard'
import { CleaningTaskFormDialog } from './components/CleaningTaskFormDialog'
import { getCleaningDueStatus, getCleaningProgress } from './status'
import { useCleaning } from './useCleaning'

interface CleaningPageProps {
  onUnauthorized: () => void
}

const ALL_CATEGORIES = 'all'

export function CleaningPage({ onUnauthorized }: CleaningPageProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const state = useCleaning({ onUnauthorized })
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
          <div className="cleaning-hero__actions">
            <Link className="secondary-button" to={{ pathname: appPaths['cleaning-reports'], search: location.search }}>
              {t('cleaning.reportLink')}
            </Link>
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
          </div>
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

          {state.selectedGroup && (
            <div className="cleaning-category-toolbar">
              <nav className="cleaning-category-filter" aria-label={t('cleaning.categoryFilter')}>
                <button
                  className={`cleaning-category-filter__button${effectiveSelectedCategory === ALL_CATEGORIES ? ' cleaning-category-filter__button--active' : ''}`}
                  type="button"
                  aria-pressed={effectiveSelectedCategory === ALL_CATEGORIES}
                  onClick={() => setSelectedCategory(ALL_CATEGORIES)}
                >
                  {t('cleaning.allCategories')}
                </button>
                {state.categories.map((category) => (
                  <button
                    className={`cleaning-category-filter__button${effectiveSelectedCategory === category.id ? ' cleaning-category-filter__button--active' : ''}`}
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
                {t('cleaning.categoryManage')}
              </button>
            </div>
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
              icon={<TaskAltIcon />}
              title={t('cleaning.groupNeeded')}
              description={t('cleaning.groupNeededHelp')}
            />
          ) : visibleActiveTasks.length === 0 ? (
            <EmptyState
              className="cleaning-empty-state"
              icon={<TaskAltIcon />}
              title={
                effectiveSelectedCategory === ALL_CATEGORIES
                  ? t('cleaning.empty')
                  : t('cleaning.emptyCategory', { category: selectedCategoryName })
              }
              description={
                state.categories.length === 0
                  ? t('cleaning.emptyNoCategoriesHelp')
                  : effectiveSelectedCategory === ALL_CATEGORIES
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
          categories={state.categories}
          submitting={state.submitting}
          error={state.dialogError}
          onSubmit={state.saveTask}
          onClose={state.closeTaskDialog}
        />
      )}
      {state.showCategoryDialog && (
        <CleaningCategoryManagerDialog
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
