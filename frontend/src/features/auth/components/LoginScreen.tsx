import { useId, useState, type FormEvent } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../../../shared/api/client'
import type { Theme } from '../../../shared/types/theme'
import { FamilyGroupIcon, LoginIcon, MoonIcon, SunIcon } from '../../../shared/ui/icons'
import { LanguageToggle } from '../../../shared/ui/LanguageToggle'

interface LoginScreenProps {
  initialError: string | null
  theme: Theme
  onLogin: (username: string, password: string) => Promise<void>
  onToggleTheme: () => void
}

function getLoginErrorMessage(error: unknown, t: TFunction): string {
  if (!(error instanceof ApiError)) return t('auth.errorConnection')
  if (error.status === 401) return t('auth.errorCredentials')
  if (error.status === 429) return t('auth.errorRateLimit')
  if (error.status === 403) return t('auth.errorOrigin')
  return t('auth.errorGeneric')
}

export function LoginScreen({ initialError, theme, onLogin, onToggleTheme }: LoginScreenProps) {
  const { t } = useTranslation()
  const usernameId = useId()
  const passwordId = useId()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(initialError)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await onLogin(username, password)
    } catch (loginError) {
      setError(getLoginErrorMessage(loginError, t))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-page__actions">
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
      <section className="login-panel" aria-labelledby="login-heading">
        <span className="brand__mark login-panel__mark">
          <FamilyGroupIcon />
        </span>
        <p className="eyebrow" lang="en">
          {t('auth.eyebrow')}
        </p>
        <h1 id="login-heading">{t('auth.title')}</h1>
        <p className="login-panel__description">{t('auth.description')}</p>
        <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
          <label htmlFor={usernameId}>{t('auth.username')}</label>
          <input
            id={usernameId}
            name="username"
            type="text"
            value={username}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            onChange={(event) => setUsername(event.target.value)}
          />
          <label htmlFor={passwordId}>{t('auth.password')}</label>
          <input
            id={passwordId}
            name="password"
            type="password"
            value={password}
            autoComplete="current-password"
            required
            onChange={(event) => setPassword(event.target.value)}
          />
          <button className="login-button icon-button" type="submit" disabled={submitting || !username || !password}>
            <LoginIcon />
            {submitting ? t('auth.signingIn') : t('auth.signIn')}
          </button>
        </form>
        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
      </section>
    </main>
  )
}
