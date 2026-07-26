import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { CancelIcon, SaveIcon } from '../../../shared/ui/icons'

interface GroupFormDialogProps {
  submitting: boolean
  error: string | null
  onSubmit: (name: string) => Promise<void>
  onClose: () => void
}

export function GroupFormDialog({ submitting, error, onSubmit, onClose }: GroupFormDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const nameId = useId()
  const [name, setName] = useState('')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !name.trim()) return
    await onSubmit(name.trim())
  }

  return (
    <Dialog titleId={headingId} className="group-form-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t('groups.create')}</h2>
        <p>{t('groups.createHelp')}</p>
      </div>
      <form className="group-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={nameId}>{t('groups.name')}</label>
        <input
          id={nameId}
          value={name}
          maxLength={120}
          required
          autoFocus
          placeholder={t('groups.namePlaceholder')}
          onChange={(event) => setName(event.target.value)}
        />
        {error && (
          <p className="dialog-error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            className="danger-button danger-button--filled icon-button"
            type="button"
            onClick={onClose}
            disabled={submitting}
          >
            <CancelIcon />
            {t('common.cancel')}
          </button>
          <button className="success-button icon-button" type="submit" disabled={submitting || !name.trim()}>
            <SaveIcon />
            {submitting ? t('groups.creating') : t('groups.create')}
          </button>
        </div>
      </form>
    </Dialog>
  )
}
