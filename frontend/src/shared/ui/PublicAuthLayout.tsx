import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { Theme } from '../types/theme'
import { LanguageToggle } from './LanguageToggle'
import { MoonIcon, SunIcon } from './icons'

interface PublicAuthLayoutProps {
  theme: Theme
  onToggleTheme: () => void
  icon: ReactNode
  eyebrow: ReactNode
  title: ReactNode
  titleId: string
  description?: ReactNode
  panelClassName?: string
  children: ReactNode
}

export function PublicAuthLayout({
  theme,
  onToggleTheme,
  icon,
  eyebrow,
  title,
  titleId,
  description,
  panelClassName,
  children,
}: PublicAuthLayoutProps) {
  const { t } = useTranslation()
  const panelClasses = ['login-panel', panelClassName].filter(Boolean).join(' ')

  return (
    <main className="login-page">
      <div className="login-page__actions">
        <LanguageToggle />
        <button
          className="theme-toggle"
          type="button"
          aria-label={t(theme === 'dark' ? 'common.lightMode' : 'common.darkMode')}
          aria-pressed={theme === 'dark'}
          onClick={onToggleTheme}
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
      <section className={panelClasses} aria-labelledby={titleId}>
        <span className="brand__mark login-panel__mark">{icon}</span>
        <p className="eyebrow">{eyebrow}</p>
        <h1 id={titleId}>{title}</h1>
        {description !== undefined && <p className="login-panel__description">{description}</p>}
        {children}
      </section>
    </main>
  )
}
