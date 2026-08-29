import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from './Dialog'
import { CancelIcon, DeleteIcon, EditIcon, PlusIcon, SaveIcon } from './icons'

export interface ManagedCategory {
  id: string
  name: string
}

export interface CategoryManagerCopy {
  title: string
  help: string
  name: string
  placeholder: string
  add: string
  noCategories: string
  moveUp: (categoryName: string) => string
  moveDown: (categoryName: string) => string
  edit: (categoryName: string) => string
  delete: (categoryName: string) => string
}

interface CategoryManagerDialogProps<T extends ManagedCategory> {
  categories: readonly T[]
  copy: CategoryManagerCopy
  idPrefix: string
  submitting: boolean
  actionId: string | null
  error: string | null
  onCreate: (categoryName: string) => Promise<boolean>
  onRename: (categoryId: string, categoryName: string) => Promise<boolean>
  onDelete: (category: T) => Promise<boolean>
  onReorder: (categoryIds: string[]) => Promise<boolean>
  onClose: () => void
}

export function CategoryManagerDialog<T extends ManagedCategory>({
  categories,
  copy,
  idPrefix,
  submitting,
  actionId,
  error,
  onCreate,
  onRename,
  onDelete,
  onReorder,
  onClose,
}: CategoryManagerDialogProps<T>) {
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

  const beginRename = (category: T) => {
    setEditingId(category.id)
    setEditingCategoryName(category.name)
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditingCategoryName('')
  }

  const handleRename = async (event: FormEvent<HTMLFormElement>, category: T) => {
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
    <Dialog titleId={headingId} className="category-manager-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{copy.title}</h2>
        <p>{copy.help}</p>
      </div>
      <form className="category-manager-form" onSubmit={(event) => void handleCreate(event)}>
        <label htmlFor={newCategoryNameId}>{copy.name}</label>
        <div className="category-manager-form__input">
          <input
            className="form-control form-control--subtle"
            id={newCategoryNameId}
            value={newCategoryName}
            maxLength={40}
            required
            autoFocus
            placeholder={copy.placeholder}
            onChange={(event) => setNewCategoryName(event.target.value)}
          />
          <button className="primary-button icon-button" type="submit" disabled={submitting || !newCategoryName.trim()}>
            <PlusIcon />
            {copy.add}
          </button>
        </div>
      </form>

      {error && (
        <p className="dialog-error" role="alert">
          {error}
        </p>
      )}

      {categories.length > 0 ? (
        <ul className="category-manager-list">
          {categories.map((category, index) => {
            const isEditing = editingId === category.id
            const busy = actionId === category.id
            return (
              <li className="category-manager-list__item" key={category.id}>
                {isEditing ? (
                  <form
                    className="category-manager-list__edit"
                    onSubmit={(event) => void handleRename(event, category)}
                  >
                    <input
                      className="form-control form-control--subtle"
                      id={`${idPrefix}-${category.id}`}
                      aria-label={copy.name}
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
                    <div className="category-manager-list__actions">
                      <div className="category-manager-list__move-actions">
                        <button
                          className="secondary-button icon-button category-manager-list__move"
                          type="button"
                          disabled={submitting || busy || index === 0}
                          aria-label={copy.moveUp(category.name)}
                          onClick={() => void moveCategory(index, -1)}
                        >
                          ↑
                        </button>
                        <button
                          className="secondary-button icon-button category-manager-list__move"
                          type="button"
                          disabled={submitting || busy || index === categories.length - 1}
                          aria-label={copy.moveDown(category.name)}
                          onClick={() => void moveCategory(index, 1)}
                        >
                          ↓
                        </button>
                      </div>
                      <button
                        className="secondary-button icon-button"
                        type="button"
                        disabled={submitting}
                        aria-label={copy.edit(category.name)}
                        onClick={() => beginRename(category)}
                      >
                        <EditIcon />
                        {t('common.edit')}
                      </button>
                      <button
                        className="danger-button icon-button"
                        type="button"
                        disabled={submitting || busy}
                        aria-label={copy.delete(category.name)}
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
        <p className="category-manager-list__empty">{copy.noCategories}</p>
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
