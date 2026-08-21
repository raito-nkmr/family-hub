import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { appPaths, getAppView } from '../../app/routes'
import type { Theme } from '../../shared/types/theme'
import { FamilyGroupIcon, MoonIcon, SunIcon } from '../../shared/ui/icons'
import { LanguageToggle } from '../../shared/ui/LanguageToggle'

interface PrivacyPageProps {
  theme: Theme
  onToggleTheme: () => void
}

export function PrivacyPage({ theme, onToggleTheme }: PrivacyPageProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const returnToCandidate = (location.state as { returnTo?: unknown } | null)?.returnTo
  const returnTo = getSafeReturnTo(returnToCandidate)

  return (
    <main className="privacy-page">
      <header className="privacy-page__header">
        <Link className="brand" to={returnTo}>
          <span className="brand__mark">
            <FamilyGroupIcon />
          </span>
          <span>
            <strong>{t('common.appName')}</strong>
            <small lang="en">HOME APPS</small>
          </span>
        </Link>
        <div className="privacy-page__actions">
          <LanguageToggle />
          <button
            className="theme-toggle"
            type="button"
            aria-label={theme === 'dark' ? t('common.lightMode') : t('common.darkMode')}
            aria-pressed={theme === 'dark'}
            onClick={onToggleTheme}
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </header>

      <article className="privacy-page__content">
        <h1>{t('privacy.title')}</h1>
        <p className="privacy-page__lead">{t('privacy.introduction')}</p>
        <p className="privacy-page__updated">{t('privacy.updated')}</p>

        <section>
          <h2>{t('privacy.scopeTitle')}</h2>
          <p>{t('privacy.scopeBody')}</p>
        </section>

        <section>
          <h2>{t('privacy.dataTitle')}</h2>
          <ul>
            <li>{t('privacy.dataAccount')}</li>
            <li>{t('privacy.dataPhotos')}</li>
            <li>{t('privacy.dataFamily')}</li>
            <li>{t('privacy.dataOperations')}</li>
          </ul>
        </section>

        <section>
          <h2>{t('privacy.purposeTitle')}</h2>
          <p>{t('privacy.purposeBody')}</p>
        </section>

        <section>
          <h2>{t('privacy.accessTitle')}</h2>
          <p>{t('privacy.accessBody')}</p>
          <p>{t('privacy.noSale')}</p>
        </section>

        <section>
          <h2>{t('privacy.storageTitle')}</h2>
          <p>{t('privacy.storageBody')}</p>
          <p>{t('privacy.retentionBody')}</p>
        </section>

        <section>
          <h2>{t('privacy.externalTitle')}</h2>
          <p>{t('privacy.externalBody')}</p>
        </section>

        <section>
          <h2>{t('privacy.browserTitle')}</h2>
          <p>{t('privacy.browserBody')}</p>
        </section>

        <section>
          <h2>{t('privacy.requestsTitle')}</h2>
          <p>{t('privacy.requestsBody')}</p>
        </section>

        <section>
          <h2>{t('privacy.changesTitle')}</h2>
          <p>{t('privacy.changesBody')}</p>
        </section>
      </article>
    </main>
  )
}

function getSafeReturnTo(candidate: unknown): string {
  if (typeof candidate !== 'string') return appPaths.home
  try {
    const url = new URL(candidate, window.location.origin)
    if (url.origin !== window.location.origin || !getAppView(url.pathname)) return appPaths.home
    return `${url.pathname}${url.search}`
  } catch {
    return appPaths.home
  }
}
