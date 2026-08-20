import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { DialogActions } from '../../../shared/ui/DialogActions'
import { SaveIcon } from '../../../shared/ui/icons'
import type { CleaningTask } from '../api'

interface CleaningTaskFormDialogProps {
  task: CleaningTask | null
  submitting: boolean
  error: string | null
  onSubmit: (name: string, intervalDays: number) => Promise<void>
  onClose: () => void
}

export function CleaningTaskFormDialog({ task, submitting, error, onSubmit, onClose }: CleaningTaskFormDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const nameId = useId()
  const intervalId = useId()
  const errorId = useId()
  const [name, setName] = useState(task?.name ?? '')
  const [intervalDays, setIntervalDays] = useState(task?.interval_days ?? 1)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !name.trim() || intervalDays < 1 || intervalDays > 3650) return
    await onSubmit(name.trim(), intervalDays)
  }

  return (
    <Dialog titleId={headingId} className="cleaning-task-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t(task ? 'cleaning.formEdit' : 'cleaning.formAdd')}</h2>
        <p>{t('cleaning.formHelp')}</p>
      </div>
      <form className="cleaning-task-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={nameId}>{t('cleaning.place')}</label>
        <input
          className="form-control form-control--subtle"
          id={nameId}
          value={name}
          maxLength={120}
          required
          autoFocus
          placeholder={t('cleaning.placePlaceholder')}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onChange={(event) => setName(event.target.value)}
        />
        <label htmlFor={intervalId}>{t('cleaning.frequency')}</label>
        <div className="cleaning-task-form__interval">
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
          <span>{t('cleaning.days')}</span>
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
            disabled={submitting || !name.trim() || !Number.isFinite(intervalDays)}
          >
            <SaveIcon />
            {submitting ? t('common.saving') : t('common.save')}
          </button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
