import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { DialogActions } from '../../../shared/ui/DialogActions'
import { SaveIcon } from '../../../shared/ui/icons'
import type { GroupMember } from '../../groups/api'
import type { ShoppingCategory, ShoppingRequest } from '../api'

interface ShoppingItemFormDialogProps {
  item: ShoppingRequest | null
  categories: ShoppingCategory[]
  members: GroupMember[]
  submitting: boolean
  error: string | null
  onSubmit: (body: { name: string; assignee_user_id: string | null; category_id: string | null }) => Promise<boolean>
  onClose: () => void
}

export function ShoppingItemFormDialog({
  item,
  categories,
  members,
  submitting,
  error,
  onSubmit,
  onClose,
}: ShoppingItemFormDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const nameId = useId()
  const assigneeId = useId()
  const categoryId = useId()
  const errorId = useId()
  const [name, setName] = useState(item?.name ?? '')
  const [assignee, setAssignee] = useState(item?.assignee_user_id ?? '')
  const [category, setCategory] = useState(item?.category_id ?? '')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedName = name.trim()
    if (submitting || !normalizedName) return
    if (
      await onSubmit({
        name: normalizedName,
        assignee_user_id: assignee || null,
        category_id: category || null,
      })
    ) {
      onClose()
    }
  }

  return (
    <Dialog titleId={headingId} className="shopping-item-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t(item ? 'shopping.itemFormEdit' : 'shopping.itemFormAdd')}</h2>
        <p>{t('shopping.itemFormHelp')}</p>
      </div>
      <form className="shopping-item-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={nameId}>{t('shopping.itemName')}</label>
        <input
          className="form-control form-control--subtle"
          id={nameId}
          value={name}
          maxLength={120}
          required
          autoFocus
          placeholder={t('shopping.itemPlaceholder')}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(event) => setName(event.target.value)}
        />

        <label htmlFor={assigneeId}>{t('shopping.assignee')}</label>
        <select
          className="form-control form-control--subtle"
          id={assigneeId}
          value={assignee}
          onChange={(event) => setAssignee(event.currentTarget.value)}
        >
          <option value="">{t('shopping.anyone')}</option>
          {members.map((member) => (
            <option key={member.user_id} value={member.user_id}>
              {member.username}
            </option>
          ))}
        </select>

        <label htmlFor={categoryId}>{t('shopping.category')}</label>
        <select
          className="form-control form-control--subtle"
          id={categoryId}
          value={category}
          onChange={(event) => setCategory(event.currentTarget.value)}
        >
          <option value="">{t('shopping.noCategory')}</option>
          {categories.map((itemCategory) => (
            <option key={itemCategory.id} value={itemCategory.id}>
              {itemCategory.name}
            </option>
          ))}
        </select>

        {error && (
          <p id={errorId} className="dialog-error" role="alert">
            {error}
          </p>
        )}
        <DialogActions disabled={submitting} onCancel={onClose}>
          <button className="success-button icon-button" type="submit" disabled={submitting || !name.trim()}>
            <SaveIcon />
            {submitting ? t('common.saving') : t('common.save')}
          </button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
