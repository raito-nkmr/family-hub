import { useCallback, useState, type PropsWithChildren } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from './Dialog'
import { CancelIcon, CheckIcon } from './icons'
import { ConfirmationContext, type ConfirmationOptions, type Confirm } from './confirmation'

export function ConfirmationDialogProvider({ children }: PropsWithChildren) {
  const { t } = useTranslation()
  const [request, setRequest] = useState<{
    message: string
    options?: ConfirmationOptions
    resolve: (confirmed: boolean) => void
  } | null>(null)
  const confirm = useCallback<Confirm>(
    (message, options) =>
      new Promise((resolve) => {
        setRequest({ message, options, resolve })
      }),
    [],
  )
  const settle = (confirmed: boolean) => {
    request?.resolve(confirmed)
    setRequest(null)
  }

  return (
    <ConfirmationContext value={confirm}>
      {children}
      {request && (
        <Dialog titleId="confirmation-dialog-title" size="compact" onClose={() => settle(false)}>
          <div className="confirmation-dialog">
            <h2 id="confirmation-dialog-title">{t('common.confirmTitle')}</h2>
            <p>{request.message}</p>
            <div className="confirmation-dialog__actions">
              <button
                className="danger-button danger-button--filled icon-button"
                type="button"
                onClick={() => settle(false)}
                data-dialog-autofocus="true"
              >
                <CancelIcon />
                {request.options?.cancelLabel ?? t('common.cancel')}
              </button>
              <button className="success-button icon-button" type="button" onClick={() => settle(true)}>
                <CheckIcon />
                {request.options?.confirmLabel ?? t('common.confirm')}
              </button>
            </div>
          </div>
        </Dialog>
      )}
    </ConfirmationContext>
  )
}
