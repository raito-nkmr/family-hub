import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

interface AppFooterProps {
  privacyCurrent?: boolean
  privacyReturnTo?: string
}

export function AppFooter({ privacyCurrent = false, privacyReturnTo }: AppFooterProps) {
  const { t } = useTranslation()

  return (
    <footer className="app-footer">
      <span>
        {t('common.appName')} · v{__APP_VERSION__}
      </span>
      <Link
        to="/privacy"
        state={privacyReturnTo ? { returnTo: privacyReturnTo } : undefined}
        aria-current={privacyCurrent ? 'page' : undefined}
      >
        {t('common.footerPrivacy')}
      </Link>
    </footer>
  )
}
