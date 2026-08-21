import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { CancelIcon, DeleteIcon, EditIcon, PlusIcon, SaveIcon } from '../../../shared/ui/icons'
import type { CleaningCategory } from '../api'

interface CleaningCategoryManagerDialogProps {
  categories: CleaningCategory[]
  submitting: boolean
  actionId: string | null
  error: string | null
  onCreate: (name: string) => Promise<boolean>
  onRename: (categoryId: string, name: string) => Promise<boolean>
  onDelete: (category: CleaningCategory) => Promise<boolean>
  onClose: () => void
}

export function CleaningCategoryManagerDialog({
  categories,
  submitting,
  actionId,
  error,
  onCreate,
  onRename,
  onDelete,
  onClose,
}: CleaningCategoryManagerDialogProps) {
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

  const beginRename = (category: CleaningCategory) => {
    setEditingId(category.id)
    setEditingName(category.name)
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditingName('')
  }

  const handleRename = async (event: FormEvent<HTMLFormElement>, category: CleaningCategory) => {
    event.preventDefault()
    const name = editingName.trim()
    if (!name || submitting) return
    if (await onRename(category.id, name)) cancelRename()
  }

  return (
    <Dialog titleId={headingId} className="cleaning-category-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t('cleaning.categoryManage')}</h2>
        <p>{t('cleaning.categoryManageHelp')}</p>
      </div>
      <form className="cleaning-category-form" onSubmit={(event) => void handleCreate(event)}>
        <label htmlFor={newNameId}>{t('cleaning.categoryName')}</label>
        <div className="cleaning-category-form__input">
          <input
            className="form-control form-control--subtle"
            id={newNameId}
            value={newName}
            maxLength={40}
            required
            autoFocus
            placeholder={t('cleaning.categoryNamePlaceholder')}
            onChange={(event) => setNewName(event.target.value)}
          />
          <button className="primary-button icon-button" type="submit" disabled={submitting || !newName.trim()}>
            <PlusIcon />
            {t('cleaning.categoryCreate')}
          </button>
        </div>
      </form>

      {error && (
        <p className="dialog-error" role="alert">
          {error}
        </p>
      )}

      {categories.length > 0 ? (
        <ul className="cleaning-category-list">
          {categories.map((category) => {
            const isEditing = editingId === category.id
            const busy = actionId === category.id
            return (
              <li className="cleaning-category-list__item" key={category.id}>
                {isEditing ? (
                  <form
                    className="cleaning-category-list__edit"
                    onSubmit={(event) => void handleRename(event, category)}
                  >
                    <input
                      className="form-control form-control--subtle"
                      id={`cleaning-category-${category.id}`}
                      aria-label={t('cleaning.categoryName')}
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
                    <div className="cleaning-category-list__actions">
                      <button
                        className="secondary-button icon-button"
                        type="button"
                        disabled={submitting}
                        aria-label={t('cleaning.editCategory', { name: category.name })}
                        onClick={() => beginRename(category)}
                      >
                        <EditIcon />
                        {t('common.edit')}
                      </button>
                      <button
                        className="danger-button icon-button"
                        type="button"
                        disabled={submitting || busy}
                        aria-label={t('cleaning.deleteCategory', { name: category.name })}
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
        <p className="cleaning-category-list__empty">{t('cleaning.noCategories')}</p>
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
