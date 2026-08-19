import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { ApkInstallIcon, CloseIcon } from '../../shared/ui/icons'

interface PwaInstallCardBaseProps {
  onShowInstallGuide: () => void
}

type PwaInstallCardProps =
  | (PwaInstallCardBaseProps & { variant: 'home'; onDismiss: () => void })
  | (PwaInstallCardBaseProps & { variant: 'account' })

const copyByVariant = {
  home: { title: 'pwa.cardTitle', description: 'pwa.cardDescription' },
  account: { title: 'pwa.accountTitle', description: 'pwa.accountDescription' },
} as const

export function PwaInstallCard(props: PwaInstallCardProps) {
  const { t } = useTranslation()
  const { variant, onShowInstallGuide } = props
  const headingId = useId()
  const copy = copyByVariant[variant]

  return (
    <section className={`pwa-install-card pwa-install-card--${variant}`} aria-labelledby={headingId}>
      <img className="pwa-install-card__icon" src="/app-icon-180.png" alt="" />
      <div className="pwa-install-card__content">
        <h2 id={headingId}>{t(copy.title)}</h2>
        <p>{t(copy.description)}</p>
      </div>
      <div className="pwa-install-card__actions">
        <button className="secondary-button icon-button" type="button" onClick={onShowInstallGuide}>
          <ApkInstallIcon />
          {t('pwa.showGuide')}
        </button>
        {props.variant === 'home' && (
          <button
            className="pwa-install-card__dismiss"
            type="button"
            aria-label={t('pwa.dismissPrompt')}
            onClick={props.onDismiss}
          >
            <CloseIcon />
          </button>
        )}
      </div>
    </section>
  )
}
