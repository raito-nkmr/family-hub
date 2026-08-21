import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { CancelIcon, DeleteIcon, EditIcon, PlusIcon, SaveIcon } from '../../../shared/ui/icons'
import type { ChoreCategory } from '../api'

interface ChoreCategoryManagerDialogProps {
  categories: ChoreCategory[]
  submitting: boolean
  actionId: string | null
  error: string | null
  onCreate: (name: string) => Promise<boolean>
  onRename: (categoryId: string, name: string) => Promise<boolean>
  onDelete: (category: ChoreCategory) => Promise<boolean>
  onReorder: (categoryIds: string[]) => Promise<boolean>
  onClose: () => void
}

export function ChoreCategoryManagerDialog({
  categories,
  submitting,
  actionId,
  error,
  onCreate,
  onRename,
  onDelete,
  onReorder,
  onClose,
}: ChoreCategoryManagerDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const newNameId = useId()
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingName, setEditingName] = useState('')

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const name = newName.trim()
    if (!name || submitting) return
    if (await onCreate(name)) setNewName('')
  }

  const beginRename = (category: ChoreCategory) => {
    setEditingId(category.id)
    setEditingName(category.name)
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditingName('')
  }

  const handleRename = async (event: FormEvent<HTMLFormElement>, category: ChoreCategory) => {
    event.preventDefault()
    const name = editingName.trim()
    if (!name || submitting) return
    if (await onRename(category.id, name)) cancelRename()
  }

  const moveCategory = async (index: number, offset: -1 | 1) => {
    const targetIndex = index + offset
    if (targetIndex < 0 || targetIndex >= categories.length || submitting) return
    const categoryIds = categories.map((category) => category.id)
    ;[categoryIds[index], categoryIds[targetIndex]] = [categoryIds[targetIndex], categoryIds[index]]
    await onReorder(categoryIds)
  }

  return (
    <Dialog titleId={headingId} className="chore-category-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t('chores.categoryManage')}</h2>
        <p>{t('chores.categoryManageHelp')}</p>
      </div>
      <form className="chore-category-form" onSubmit={(event) => void handleCreate(event)}>
        <label htmlFor={newNameId}>{t('chores.categoryName')}</label>
        <div className="chore-category-form__input">
          <input
            className="form-control form-control--subtle"
            id={newNameId}
            value={newName}
            maxLength={40}
            required
            autoFocus
            placeholder={t('chores.categoryNamePlaceholder')}
            onChange={(event) => setNewName(event.target.value)}
          />
          <button className="primary-button icon-button" type="submit" disabled={submitting || !newName.trim()}>
            <PlusIcon />
            {t('chores.categoryCreate')}
          </button>
        </div>
      </form>

      {error && (
        <p className="dialog-error" role="alert">
          {error}
        </p>
      )}

      {categories.length > 0 ? (
        <ul className="chore-category-list">
          {categories.map((category, index) => {
            const isEditing = editingId === category.id
            const busy = actionId === category.id
            return (
              <li className="chore-category-list__item" key={category.id}>
                {isEditing ? (
                  <form className="chore-category-list__edit" onSubmit={(event) => void handleRename(event, category)}>
                    <input
                      className="form-control form-control--subtle"
                      id={`chore-category-${category.id}`}
                      aria-label={t('chores.categoryName')}
                      value={editingName}
                      maxLength={40}
                      required
                      onChange={(event) => setEditingName(event.target.value)}
                    />
                    <button
                      className="success-button icon-button"
                      type="submit"
                      disabled={submitting || !editingName.trim()}
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
                    <div className="chore-category-list__actions">
                      <div className="chore-category-list__move-actions">
                        <button
                          className="secondary-button icon-button chore-category-list__move"
                          type="button"
                          disabled={submitting || busy || index === 0}
                          aria-label={t('chores.moveCategoryUp', { name: category.name })}
                          onClick={() => void moveCategory(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          className="secondary-button icon-button chore-category-list__move"
                          type="button"
                          disabled={submitting || busy || index === categories.length - 1}
                          aria-label={t('chores.moveCategoryDown', { name: category.name })}
                          onClick={() => void moveCategory(index, 1)}
                        >
                          ↓
                        </button>
                      </div>
                      <button
                        className="secondary-button icon-button"
                        type="button"
                        disabled={submitting}
                        aria-label={t('chores.editCategory', { name: category.name })}
                        onClick={() => beginRename(category)}
                      >
                        <EditIcon />
                        {t('common.edit')}
                      </button>
                      <button
                        className="danger-button icon-button"
                        type="button"
                        disabled={submitting || busy}
                        aria-label={t('chores.deleteCategory', { name: category.name })}
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
        <p className="chore-category-list__empty">{t('chores.noCategories')}</p>
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
