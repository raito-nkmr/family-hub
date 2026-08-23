import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CategoryIcon, DeleteIcon, EditIcon, PlusIcon, ShoppingCartIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import { useConfirmation } from '../../shared/ui/confirmation'
import type { ShoppingCategory, ShoppingRequest } from './api'
import { ShoppingCategoryManagerDialog } from './components/ShoppingCategoryManagerDialog'
import { ShoppingItemFormDialog } from './components/ShoppingItemFormDialog'
import { useShoppingList } from './useShoppingWorkflow'

interface ShoppingListPageProps {
  onUnauthorized: () => void
}

const ALL_CATEGORIES = 'all'
const NO_CATEGORY = 'none'

export function ShoppingListPage({ onUnauthorized }: ShoppingListPageProps) {
  const { t } = useTranslation()
  const confirm = useConfirmation()
  const state = useShoppingList({ onUnauthorized })
  const [selectedCategory, setSelectedCategory] = useState(ALL_CATEGORIES)
  const [showItemDialog, setShowItemDialog] = useState(false)
  const [editingItem, setEditingItem] = useState<ShoppingRequest | null>(null)
  const [showCategoryDialog, setShowCategoryDialog] = useState(false)

  const effectiveSelectedCategory =
    selectedCategory === ALL_CATEGORIES ||
    selectedCategory === NO_CATEGORY ||
    state.categories.some((category) => category.id === selectedCategory)
      ? selectedCategory
      : ALL_CATEGORIES
  const selectedCategoryName =
    state.categories.find((category) => category.id === effectiveSelectedCategory)?.name ?? ''
  const visibleItems = state.items.filter((item) => matchesCategory(item.category_id, effectiveSelectedCategory))
  const emptyListMessage =
    effectiveSelectedCategory === ALL_CATEGORIES
      ? t('shopping.listEmpty')
      : t('shopping.listEmptyCategory', {
          categoryName: selectedCategoryName || t('shopping.noCategory'),
        })

  const openAddDialog = () => {
    state.clearDialogError()
    setEditingItem(null)
    setShowItemDialog(true)
  }

  const openEditDialog = (item: ShoppingRequest) => {
    state.clearDialogError()
    setEditingItem(item)
    setShowItemDialog(true)
  }

  const closeItemDialog = () => {
    setShowItemDialog(false)
    setEditingItem(null)
  }

  const handleSelectGroup = async (groupId: string) => {
    setSelectedCategory(ALL_CATEGORIES)
    closeItemDialog()
    setShowCategoryDialog(false)
    await state.selectGroup(groupId)
  }

  const saveItem = (body: { name: string; assignee_user_id: string | null; category_id: string | null }) =>
    state.saveRequest(editingItem ?? undefined, body)

  const removeItem = async (item: ShoppingRequest) => {
    if (!(await confirm(t('shopping.deleteConfirm', { itemName: item.name })))) return
    await state.removeRequest(item.id)
  }

  const removeCategory = async (category: ShoppingCategory) => {
    if (!(await confirm(t('errors.shoppingCategoryDeleteConfirm', { categoryName: category.name })))) return false
    const removed = await state.removeCategory(category.id)
    if (removed && selectedCategory === category.id) setSelectedCategory(ALL_CATEGORIES)
    return removed
  }

  return (
    <>
      <main id="top" className="shopping-page">
        <section className="shopping-hero shopping-hero--compact shopping-hero--with-action">
          <div>
            <p className="eyebrow">{t('shopping.listEyebrow')}</p>
            <h1>{t('shopping.listTitle')}</h1>
            <p>{t('shopping.listDescription')}</p>
          </div>
          <div className="shopping-hero__actions">
            <button
              className="primary-button icon-button"
              type="button"
              disabled={state.loading || state.submitting || state.groups.length === 0}
              onClick={openAddDialog}
            >
              <PlusIcon />
              {t('shopping.add')}
            </button>
          </div>
        </section>

        <section className="shopping-board shopping-management" aria-labelledby="shopping-list-heading">
          <GroupScopedToolbar
            groups={state.groups}
            selectedGroupId={state.selectedGroupId}
            selectId="shopping-list-group"
            label={t('shopping.group')}
            selectDisabled={state.loading || state.submitting || state.groups.length === 0}
            refreshDisabled={state.loading || state.submitting}
            onSelectGroup={handleSelectGroup}
            onRefresh={state.refresh}
          />
          {state.pageError && <PageMessage>{state.pageError}</PageMessage>}

          {state.groups.length === 0 ? (
            <EmptyState
              icon={<ShoppingCartIcon />}
              title={t('shopping.groupNeeded')}
              description={t('shopping.groupNeededHelp')}
            />
          ) : (
            <>
              <div className="shopping-category-toolbar">
                <nav className="shopping-category-filter" aria-label={t('shopping.categoryFilter')}>
                  <button
                    className={`shopping-category-filter__button${effectiveSelectedCategory === ALL_CATEGORIES ? ' shopping-category-filter__button--active' : ''}`}
                    type="button"
                    aria-pressed={effectiveSelectedCategory === ALL_CATEGORIES}
                    onClick={() => setSelectedCategory(ALL_CATEGORIES)}
                  >
                    {t('shopping.allCategories')}
                  </button>
                  {state.categories.map((category) => (
                    <button
                      className={`shopping-category-filter__button${effectiveSelectedCategory === category.id ? ' shopping-category-filter__button--active' : ''}`}
                      key={category.id}
                      type="button"
                      aria-pressed={effectiveSelectedCategory === category.id}
                      onClick={() => setSelectedCategory(category.id)}
                    >
                      {category.name}
                    </button>
                  ))}
                  <button
                    className={`shopping-category-filter__button${effectiveSelectedCategory === NO_CATEGORY ? ' shopping-category-filter__button--active' : ''}`}
                    type="button"
                    aria-pressed={effectiveSelectedCategory === NO_CATEGORY}
                    onClick={() => setSelectedCategory(NO_CATEGORY)}
                  >
                    {t('shopping.noCategory')}
                  </button>
                </nav>
                <button
                  className="secondary-button icon-button"
                  type="button"
                  disabled={state.submitting}
                  onClick={() => {
                    state.clearCategoryDialogError()
                    setShowCategoryDialog(true)
                  }}
                >
                  <CategoryIcon />
                  {t('shopping.categoryManage')}
                </button>
              </div>

              <div className="section-heading shopping-management__heading">
                <div>
                  <h2 id="shopping-list-heading">{t('shopping.list')}</h2>
                  <p>
                    {visibleItems.length > 0
                      ? t('shopping.listCount', { count: visibleItems.length })
                      : emptyListMessage}
                  </p>
                </div>
              </div>

              {state.loading ? (
                <div className="shopping-management-list" aria-label={t('shopping.loading')}>
                  {Array.from({ length: 4 }, (_, index) => (
                    <div className="shopping-management-item shopping-management-item--skeleton" key={index} />
                  ))}
                </div>
              ) : visibleItems.length === 0 ? (
                <p className="shopping-muted">{emptyListMessage}</p>
              ) : (
                <div className="shopping-management-list">
                  {visibleItems.map((item) => (
                    <article className="shopping-management-item" key={item.id}>
                      <div>
                        <h3>{item.name}</h3>
                        <p>
                          {item.assignee_username
                            ? t('shopping.requestedTo', { username: item.assignee_username })
                            : t('shopping.anyone')}
                          {item.category_name ? ` · ${item.category_name}` : ` · ${t('shopping.noCategory')}`}
                        </p>
                      </div>
                      <div className="shopping-management-item__actions">
                        <button
                          className="secondary-button icon-button"
                          type="button"
                          disabled={state.submitting}
                          aria-label={t('shopping.editItem', { itemName: item.name })}
                          onClick={() => openEditDialog(item)}
                        >
                          <EditIcon />
                          {t('common.edit')}
                        </button>
                        <button
                          className="danger-button icon-button"
                          type="button"
                          disabled={state.submitting}
                          aria-label={t('shopping.deleteItem', { itemName: item.name })}
                          onClick={() => void removeItem(item)}
                        >
                          <DeleteIcon />
                          {t('common.delete')}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </main>

      {showItemDialog && (
        <ShoppingItemFormDialog
          item={editingItem}
          categories={state.categories}
          members={state.members}
          submitting={state.submitting}
          error={state.dialogError}
          onSubmit={saveItem}
          onClose={closeItemDialog}
        />
      )}
      {showCategoryDialog && (
        <ShoppingCategoryManagerDialog
          categories={state.categories}
          submitting={state.submitting}
          actionId={state.categoryActionId}
          error={state.categoryDialogError}
          onCreate={state.addCategory}
          onRename={state.renameCategory}
          onDelete={removeCategory}
          onReorder={state.reorderCategories}
          onClose={() => setShowCategoryDialog(false)}
        />
      )}
    </>
  )
}

function matchesCategory(categoryId: string | null, selectedCategory: string): boolean {
  return (
    selectedCategory === ALL_CATEGORIES ||
    (selectedCategory === NO_CATEGORY ? categoryId === null : categoryId === selectedCategory)
  )
}
