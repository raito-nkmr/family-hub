import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { DialogActions } from '../../../shared/ui/DialogActions'
import { SaveIcon } from '../../../shared/ui/icons'
import type { ChoreCategory, ChoreTask } from '../api'

interface ChoreTaskFormDialogProps {
  task: ChoreTask | null
  categories: ChoreCategory[]
  submitting: boolean
  error: string | null
  onSubmit: (name: string, intervalDays: number, categoryId: string) => Promise<void>
  onClose: () => void
}

export function ChoreTaskFormDialog({
  task,
  categories,
  submitting,
  error,
  onSubmit,
  onClose,
}: ChoreTaskFormDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const nameId = useId()
  const intervalId = useId()
  const categoryFieldId = useId()
  const errorId = useId()
  const [name, setName] = useState(task?.name ?? '')
  const [intervalDays, setIntervalDays] = useState(task?.interval_days ?? 1)
  const [categoryId, setCategoryId] = useState(task?.category_id ?? categories[0]?.id ?? '')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !name.trim() || intervalDays < 1 || intervalDays > 3650) return
    if (!categoryId) return
    await onSubmit(name.trim(), intervalDays, categoryId)
  }

  return (
    <Dialog titleId={headingId} className="chore-task-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t(task ? 'chores.formEdit' : 'chores.formAdd')}</h2>
        <p>{t('chores.formHelp')}</p>
      </div>
      <form className="chore-task-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={nameId}>{t('chores.place')}</label>
        <input
          className="form-control form-control--subtle"
          id={nameId}
          value={name}
          maxLength={120}
          required
          autoFocus
          placeholder={t('chores.placePlaceholder')}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(event) => setName(event.target.value)}
        />
        <label htmlFor={categoryFieldId}>{t('chores.category')}</label>
        {categories.length > 0 ? (
          <select
            className="form-control form-control--subtle"
            id={categoryFieldId}
            value={categoryId}
            onChange={(event) => setCategoryId(event.currentTarget.value)}
          >
            {categories.map((category) => (
              <option value={category.id} key={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        ) : (
          <p className="form-help">{t('chores.noCategoriesForTask')}</p>
        )}
        <label htmlFor={intervalId}>{t('chores.frequency')}</label>
        <div className="chore-task-form__interval">
          <input
            className="form-control form-control--subtle"
            id={intervalId}
            type="number"
            inputMode="numeric"
            min={1}
            max={3650}
            required
            value={intervalDays}
            onChange={(event) => setIntervalDays(event.currentTarget.valueAsNumber)}
          />
          <span>{t('chores.days')}</span>
        </div>
        {error && (
          <p id={errorId} className="dialog-error" role="alert">
            {error}
          </p>
        )}
        <DialogActions disabled={submitting} onCancel={onClose}>
          <button
            className="success-button icon-button"
            type="submit"
            disabled={submitting || !name.trim() || !Number.isFinite(intervalDays) || !categoryId}
          >
            <SaveIcon />
            {submitting ? t('common.saving') : t('common.save')}
          </button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
