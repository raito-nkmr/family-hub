import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { DeleteIcon, EditIcon, PlusIcon, SaveIcon, ShoppingCartIcon } from '../../shared/ui/icons'
import { EmptyState } from '../../shared/ui/EmptyState'
import { GroupScopedToolbar } from '../../shared/ui/GroupScopedToolbar'
import { PageMessage } from '../../shared/ui/PageMessage'
import type { ShoppingRequest } from './api'
import { useShoppingList } from './useShoppingWorkflow'

interface ShoppingListPageProps {
  onUnauthorized: () => void
}

export function ShoppingListPage({ onUnauthorized }: ShoppingListPageProps) {
  const { t } = useTranslation()
  const state = useShoppingList({ onUnauthorized })
  const [name, setName] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')
  const [editingAssigneeId, setEditingAssigneeId] = useState('')
  const [editingItemCategoryId, setEditingItemCategoryId] = useState('')
  const [categoryName, setCategoryName] = useState('')
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null)
  const [editingCategoryName, setEditingCategoryName] = useState('')

  const clearItemForm = () => {
    setName('')
    setAssigneeId('')
    setCategoryId('')
  }

  const submitNewItem = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedName = name.trim()
    if (!normalizedName) return
    if (
      await state.saveRequest(undefined, {
        name: normalizedName,
        assignee_user_id: assigneeId || null,
        category_id: categoryId || null,
      })
    ) {
      clearItemForm()
    }
  }

  const beginEdit = (item: ShoppingRequest) => {
    setEditingId(item.id)
    setEditingName(item.name)
    setEditingAssigneeId(item.assignee_user_id ?? '')
    setEditingItemCategoryId(item.category_id ?? '')
  }

  const saveEdit = async (item: ShoppingRequest) => {
    const normalizedName = editingName.trim()
    if (!normalizedName) return
    if (
      await state.saveRequest(item, {
        name: normalizedName,
        assignee_user_id: editingAssigneeId || null,
        category_id: editingItemCategoryId || null,
      })
    ) {
      setEditingId(null)
    }
  }

  const removeItem = async (item: ShoppingRequest) => {
    if (!window.confirm(t('shopping.deleteConfirm', { itemName: item.name }))) return
    await state.removeRequest(item.id)
  }

  const submitCategory = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedName = categoryName.trim()
    if (!normalizedName) return
    if (await state.addCategory(normalizedName)) setCategoryName('')
  }

  const renameCategory = async (id: string) => {
    const normalizedName = editingCategoryName.trim()
    if (!normalizedName) return
    if (await state.renameCategory(id, normalizedName)) setEditingCategoryId(null)
  }

  const moveCategory = async (index: number, offset: -1 | 1) => {
    const target = index + offset
    if (target < 0 || target >= state.categories.length) return
    const ids = state.categories.map((category) => category.id)
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    await state.reorderCategories(ids)
  }

  return (
    <main id="top" className="shopping-page">
      <section className="shopping-hero shopping-hero--compact">
        <p className="eyebrow">{t('shopping.listEyebrow')}</p>
        <h1>{t('shopping.listTitle')}</h1>
        <p>{t('shopping.listDescription')}</p>
      </section>

      <section className="shopping-board shopping-management">
        <GroupScopedToolbar
          groups={state.groups}
          selectedGroupId={state.selectedGroupId}
          selectId="shopping-list-group"
          label={t('shopping.group')}
          selectDisabled={state.loading || state.submitting || state.groups.length === 0}
          refreshDisabled={state.loading || state.submitting}
          onSelectGroup={state.selectGroup}
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
            <form className="shopping-add shopping-add--management" onSubmit={(event) => void submitNewItem(event)}>
              <label htmlFor="shopping-list-item-name">{t('shopping.itemName')}</label>
              <div className="shopping-form-grid">
                <input
                  className="form-control"
                  id="shopping-list-item-name"
                  value={name}
                  maxLength={120}
                  placeholder={t('shopping.itemPlaceholder')}
                  disabled={state.submitting}
                  onChange={(event) => setName(event.target.value)}
                />
                <select
                  className="form-control"
                  value={assigneeId}
                  disabled={state.submitting}
                  onChange={(event) => setAssigneeId(event.target.value)}
                >
                  <option value="">{t('shopping.anyone')}</option>
                  {state.members.map((member) => (
                    <option key={member.user_id} value={member.user_id}>
                      {member.username}
                    </option>
                  ))}
                </select>
                <select
                  className="form-control"
                  value={categoryId}
                  disabled={state.submitting}
                  onChange={(event) => setCategoryId(event.target.value)}
                >
                  <option value="">{t('shopping.noCategory')}</option>
                  {state.categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
                <button
                  className="primary-button icon-button"
                  type="submit"
                  disabled={state.submitting || !name.trim()}
                >
                  <PlusIcon />
                  {t('shopping.add')}
                </button>
              </div>
            </form>

            <div className="shopping-management__section">
              <div className="section-heading">
                <div>
                  <h2>{t('shopping.list')}</h2>
                  <p>{t('shopping.listManagementHelp')}</p>
                </div>
              </div>
              {state.loading ? (
                <p>{t('shopping.loading')}</p>
              ) : state.items.length === 0 ? (
                <p className="shopping-muted">{t('shopping.listEmpty')}</p>
              ) : (
                <div className="shopping-management-list">
                  {state.items.map((item) => {
                    const editing = editingId === item.id
                    return (
                      <article className="shopping-management-item" key={item.id}>
                        {editing ? (
                          <div className="shopping-management-item__edit">
                            <input
                              className="form-control"
                              value={editingName}
                              maxLength={120}
                              onChange={(event) => setEditingName(event.target.value)}
                            />
                            <select
                              className="form-control"
                              value={editingAssigneeId}
                              onChange={(event) => setEditingAssigneeId(event.target.value)}
                            >
                              <option value="">{t('shopping.anyone')}</option>
                              {state.members.map((member) => (
                                <option key={member.user_id} value={member.user_id}>
                                  {member.username}
                                </option>
                              ))}
                            </select>
                            <select
                              className="form-control"
                              value={editingItemCategoryId}
                              onChange={(event) => setEditingItemCategoryId(event.target.value)}
                            >
                              <option value="">{t('shopping.noCategory')}</option>
                              {state.categories.map((category) => (
                                <option key={category.id} value={category.id}>
                                  {category.name}
                                </option>
                              ))}
                            </select>
                            <div className="shopping-management-item__actions">
                              <button
                                className="success-button icon-button"
                                type="button"
                                disabled={state.submitting || !editingName.trim()}
                                onClick={() => void saveEdit(item)}
                              >
                                <SaveIcon />
                                {t('common.save')}
                              </button>
                              <button
                                className="secondary-button"
                                type="button"
                                disabled={state.submitting}
                                onClick={() => setEditingId(null)}
                              >
                                {t('common.cancel')}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div>
                              <h3>{item.name}</h3>
                              <p>
                                {item.assignee_username
                                  ? t('shopping.requestedTo', { username: item.assignee_username })
                                  : t('shopping.anyone')}
                                {item.category_name ? ` · ${item.category_name}` : ''}
                              </p>
                            </div>
                            <div className="shopping-management-item__actions">
                              <button
                                className="secondary-button icon-button"
                                type="button"
                                onClick={() => beginEdit(item)}
                              >
                                <EditIcon />
                                {t('common.edit')}
                              </button>
                              <button
                                className="danger-button icon-button"
                                type="button"
                                onClick={() => void removeItem(item)}
                              >
                                <DeleteIcon />
                                {t('common.delete')}
                              </button>
                            </div>
                          </>
                        )}
                      </article>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="shopping-category-manager">
              <div className="section-heading">
                <div>
                  <h2>{t('shopping.categoryManage')}</h2>
                  <p>{t('shopping.categoryManageHelp')}</p>
                </div>
              </div>
              <form className="shopping-category-manager__add" onSubmit={(event) => void submitCategory(event)}>
                <input
                  className="form-control"
                  value={categoryName}
                  maxLength={40}
                  placeholder={t('shopping.categoryPlaceholder')}
                  onChange={(event) => setCategoryName(event.target.value)}
                />
                <button
                  className="primary-button icon-button"
                  type="submit"
                  disabled={state.submitting || !categoryName.trim()}
                >
                  <PlusIcon />
                  {t('shopping.categoryAdd')}
                </button>
              </form>
              <div className="shopping-category-list">
                {state.categories.map((category, index) => (
                  <div className="shopping-category-list__item" key={category.id}>
                    {editingCategoryId === category.id ? (
                      <input
                        className="form-control"
                        value={editingCategoryName}
                        maxLength={40}
                        onChange={(event) => setEditingCategoryName(event.target.value)}
                      />
                    ) : (
                      <strong>{category.name}</strong>
                    )}
                    <div className="shopping-category-list__actions">
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={index === 0 || state.submitting}
                        onClick={() => void moveCategory(index, -1)}
                      >
                        ↑
                      </button>
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={index === state.categories.length - 1 || state.submitting}
                        onClick={() => void moveCategory(index, 1)}
                      >
                        ↓
                      </button>
                      {editingCategoryId === category.id ? (
                        <button
                          className="success-button icon-button"
                          type="button"
                          disabled={state.submitting || !editingCategoryName.trim()}
                          onClick={() => void renameCategory(category.id)}
                        >
                          <SaveIcon />
                          {t('common.save')}
                        </button>
                      ) : (
                        <button
                          className="secondary-button icon-button"
                          type="button"
                          onClick={() => {
                            setEditingCategoryId(category.id)
                            setEditingCategoryName(category.name)
                          }}
                        >
                          <EditIcon />
                          {t('common.edit')}
                        </button>
                      )}
                      <button
                        className="danger-button icon-button"
                        type="button"
                        disabled={state.submitting}
                        onClick={() => void state.removeCategory(category.id)}
                      >
                        <DeleteIcon />
                        {t('common.delete')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </section>
    </main>
  )
}
