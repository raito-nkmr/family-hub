import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { appPaths } from '../../app/routes'
import type { Theme } from '../types/theme'
import { FamilyGroupIcon, LogoutIcon, MoonIcon, SunIcon } from './icons'
import { LanguageToggle } from './LanguageToggle'

interface AppHeaderProps {
  username: string
  theme: Theme
  status?: ReactNode
  onLogout: () => void
  onToggleTheme: () => void
}

export function AppHeader({ username, theme, status, onLogout, onToggleTheme }: AppHeaderProps) {
  const { t } = useTranslation()
  return (
    <header className="site-header">
      <Link className="brand" to={appPaths.home} aria-label={t('header.home')}>
        <span className="brand__mark">
          <FamilyGroupIcon />
        </span>
        <span>
          <strong>Family Hub</strong>
          <small lang="en">HOME APPS</small>
        </span>
      </Link>
      <div className="header-actions">
        {status}
        <span className="current-user">{username}</span>
        <LanguageToggle />
        <button className="logout-button" type="button" onClick={onLogout}>
          <LogoutIcon />
          {t('header.logout')}
        </button>
        <button
          className="theme-toggle"
          type="button"
          aria-label={theme === 'dark' ? t('common.lightMode') : t('common.darkMode')}
          aria-pressed={theme === 'dark'}
          title={theme === 'dark' ? t('common.lightModeTitle') : t('common.darkModeTitle')}
          onClick={onToggleTheme}
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </header>
  )
}
