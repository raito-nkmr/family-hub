import { useTranslation } from 'react-i18next'
import { Dialog } from '../../shared/ui/Dialog'
import { CheckIcon } from '../../shared/ui/icons'

interface PwaInstallGuideProps {
  onClose: () => void
}

export function PwaInstallGuide({ onClose }: PwaInstallGuideProps) {
  const { t } = useTranslation()

  return (
    <Dialog titleId="pwa-install-guide-title" className="pwa-guide" onClose={onClose}>
      <div className="pwa-guide__heading">
        <img src="/app-icon-180.png" alt="" />
        <div>
          <p className="pwa-guide__eyebrow">{t('pwa.eyebrow')}</p>
          <h2 id="pwa-install-guide-title">{t('pwa.guideTitle')}</h2>
        </div>
      </div>
      <p className="pwa-guide__intro">{t('pwa.guideIntro')}</p>
      <ol className="pwa-guide__steps">
        <li>
          <strong>{t('pwa.stepShareTitle')}</strong>
          <span>{t('pwa.stepShareBody')}</span>
        </li>
        <li>
          <strong>{t('pwa.stepAddTitle')}</strong>
          <span>{t('pwa.stepAddBody')}</span>
        </li>
        <li>
          <strong>{t('pwa.stepOpenTitle')}</strong>
          <span>{t('pwa.stepOpenBody')}</span>
        </li>
        <li>
          <strong>{t('pwa.stepDoneTitle')}</strong>
          <span>{t('pwa.stepDoneBody')}</span>
        </li>
      </ol>
      <p className="pwa-guide__note">{t('pwa.guideNote')}</p>
      <button className="success-button icon-button pwa-guide__done" type="button" onClick={onClose}>
        <CheckIcon />
        {t('common.done')}
      </button>
    </Dialog>
  )
}
