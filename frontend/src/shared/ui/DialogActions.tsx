import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CancelIcon } from './icons'

interface DialogActionsProps {
  disabled: boolean
  onCancel: () => void
  children: ReactNode
}

export function DialogActions({ disabled, onCancel, children }: DialogActionsProps) {
  const { t } = useTranslation()

  return (
    <div className="dialog-actions">
      <button
        className="danger-button danger-button--filled icon-button"
        type="button"
        onClick={onCancel}
        disabled={disabled}
      >
        <CancelIcon />
        {t('common.cancel')}
      </button>
      {children}
    </div>
  )
}
