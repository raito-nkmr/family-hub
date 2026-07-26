import { useTranslation } from 'react-i18next'
import type { AppLanguage } from '../../i18n'

export function LanguageToggle() {
  const { t, i18n } = useTranslation()
  const currentLanguage: AppLanguage = i18n.resolvedLanguage === 'ja' ? 'ja' : 'en'
  const nextLanguage: AppLanguage = currentLanguage === 'en' ? 'ja' : 'en'
  const label = t('language.switchTo', { language: t('language.' + nextLanguage) })

  return (
    <button
      className="language-toggle"
      type="button"
      lang="en"
      aria-label={label}
      title={label}
      onClick={() => void i18n.changeLanguage(nextLanguage)}
    >
      {t('language.' + nextLanguage)}
    </button>
  )
}
