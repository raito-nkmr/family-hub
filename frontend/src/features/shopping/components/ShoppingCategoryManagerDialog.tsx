import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { CancelIcon, DeleteIcon, EditIcon, PlusIcon, SaveIcon } from '../../../shared/ui/icons'
import type { ShoppingCategory } from '../api'

interface ShoppingCategoryManagerDialogProps {
  categories: ShoppingCategory[]
  submitting: boolean
  actionId: string | null
  error: string | null
  onCreate: (categoryName: string) => Promise<boolean>
  onRename: (categoryId: string, categoryName: string) => Promise<boolean>
  onDelete: (category: ShoppingCategory) => Promise<boolean>
  onReorder: (categoryIds: string[]) => Promise<boolean>
  onClose: () => void
}

export function ShoppingCategoryManagerDialog({
  categories,
  submitting,
  actionId,
  error,
  onCreate,
  onRename,
  onDelete,
  onReorder,
  onClose,
}: ShoppingCategoryManagerDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const newCategoryNameId = useId()
  const [newCategoryName, setNewCategoryName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingCategoryName, setEditingCategoryName] = useState('')

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const categoryName = newCategoryName.trim()
    if (!categoryName || submitting) return
    if (await onCreate(categoryName)) setNewCategoryName('')
  }

  const beginRename = (category: ShoppingCategory) => {
    setEditingId(category.id)
    setEditingCategoryName(category.name)
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditingCategoryName('')
  }

  const handleRename = async (event: FormEvent<HTMLFormElement>, category: ShoppingCategory) => {
    event.preventDefault()
    const categoryName = editingCategoryName.trim()
    if (!categoryName || submitting) return
    if (await onRename(category.id, categoryName)) cancelRename()
  }

  const moveCategory = async (index: number, offset: -1 | 1) => {
    const targetIndex = index + offset
    if (targetIndex < 0 || targetIndex >= categories.length || submitting) return
    const categoryIds = categories.map((category) => category.id)
    ;[categoryIds[index], categoryIds[targetIndex]] = [categoryIds[targetIndex], categoryIds[index]]
    await onReorder(categoryIds)
  }

  return (
    <Dialog titleId={headingId} className="shopping-category-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t('shopping.categoryManage')}</h2>
        <p>{t('shopping.categoryManageHelp')}</p>
      </div>
      <form className="shopping-category-form" onSubmit={(event) => void handleCreate(event)}>
        <label htmlFor={newCategoryNameId}>{t('shopping.categoryName')}</label>
        <div className="shopping-category-form__input">
          <input
            className="form-control form-control--subtle"
            id={newCategoryNameId}
            value={newCategoryName}
            maxLength={40}
            required
            autoFocus
            placeholder={t('shopping.categoryPlaceholder')}
            onChange={(event) => setNewCategoryName(event.target.value)}
          />
          <button className="primary-button icon-button" type="submit" disabled={submitting || !newCategoryName.trim()}>
            <PlusIcon />
            {t('shopping.categoryAdd')}
          </button>
        </div>
      </form>

      {error && (
        <p className="dialog-error" role="alert">
          {error}
        </p>
      )}

      {categories.length > 0 ? (
        <ul className="shopping-category-list">
          {categories.map((category, index) => {
            const isEditing = editingId === category.id
            const busy = actionId === category.id
            return (
              <li className="shopping-category-list__item" key={category.id}>
                {isEditing ? (
                  <form
                    className="shopping-category-list__edit"
                    onSubmit={(event) => void handleRename(event, category)}
                  >
                    <input
                      className="form-control form-control--subtle"
                      id={`shopping-category-${category.id}`}
                      aria-label={t('shopping.categoryName')}
                      value={editingCategoryName}
                      maxLength={40}
                      required
                      onChange={(event) => setEditingCategoryName(event.target.value)}
                    />
                    <button
                      className="success-button icon-button"
                      type="submit"
                      disabled={submitting || !editingCategoryName.trim()}
                    >
                      <SaveIcon />
                      {t('common.save')}
                    </button>
                    <button
                      className="secondary-button icon-button"
                      type="button"
                      disabled={submitting}
                      onClick={cancelRename}
                    >
                      <CancelIcon />
                      {t('common.cancel')}
                    </button>
                  </form>
                ) : (
                  <>
                    <strong>{category.name}</strong>
                    <div className="shopping-category-list__actions">
                      <div className="shopping-category-list__move-actions">
                        <button
                          className="secondary-button icon-button shopping-category-list__move"
                          type="button"
                          disabled={submitting || busy || index === 0}
                          aria-label={t('shopping.moveCategoryUp', { categoryName: category.name })}
                          onClick={() => void moveCategory(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          className="secondary-button icon-button shopping-category-list__move"
                          type="button"
                          disabled={submitting || busy || index === categories.length - 1}
                          aria-label={t('shopping.moveCategoryDown', { categoryName: category.name })}
                          onClick={() => void moveCategory(index, 1)}
                        >
                          ↓
                        </button>
                      </div>
                      <button
                        className="secondary-button icon-button"
                        type="button"
                        disabled={submitting}
                        aria-label={t('shopping.editCategory', { categoryName: category.name })}
                        onClick={() => beginRename(category)}
                      >
                        <EditIcon />
                        {t('common.edit')}
                      </button>
                      <button
                        className="danger-button icon-button"
                        type="button"
                        disabled={submitting || busy}
                        aria-label={t('shopping.deleteCategory', { categoryName: category.name })}
                        onClick={() => void onDelete(category)}
                      >
                        <DeleteIcon />
                        {t('common.delete')}
                      </button>
                    </div>
                  </>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="shopping-category-list__empty">{t('shopping.noCategories')}</p>
      )}

      <div className="dialog-actions">
        <button className="secondary-button icon-button" type="button" onClick={onClose} disabled={submitting}>
          <CancelIcon />
          {t('common.close')}
        </button>
      </div>
    </Dialog>
  )
}
