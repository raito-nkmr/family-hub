import { useId, useState, type FormEvent } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../../shared/api/client'
import type { Theme } from '../../shared/types/theme'
import { CheckIcon, LoginIcon, MoonIcon, PersonAddIcon, SunIcon } from '../../shared/ui/icons'
import { LanguageToggle } from '../../shared/ui/LanguageToggle'
import { acceptInvitation } from './api'

const MINIMUM_PASSWORD_LENGTH = 8

interface InvitationAcceptanceScreenProps {
  token: string
  theme: Theme
  onContinueToLogin: () => void
  onToggleTheme: () => void
}

function getAcceptanceError(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && error.status === 400) {
    return t('invitations.invalid')
  }
  if (error instanceof ApiError && error.status === 403) {
    return t('invitations.origin')
  }
  return t('invitations.createFailed')
}

export function InvitationAcceptanceScreen({
  token,
  theme,
  onContinueToLogin,
  onToggleTheme,
}: InvitationAcceptanceScreenProps) {
  const { t } = useTranslation()
  const passwordId = useId()
  const confirmationId = useId()
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [createdUsername, setCreatedUsername] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting) return
    if (password !== confirmation) {
      setError(t('invitations.mismatch'))
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const user = await acceptInvitation(token, password)
      setCreatedUsername(user.username)
    } catch (requestError) {
      setError(getAcceptanceError(requestError, t))
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
          aria-label={t(theme === 'dark' ? 'common.lightMode' : 'common.darkMode')}
          aria-pressed={theme === 'dark'}
          onClick={onToggleTheme}
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
      <section className="login-panel invitation-acceptance" aria-labelledby="invitation-acceptance-heading">
        <span className="brand__mark login-panel__mark">
          <PersonAddIcon />
        </span>
        <p className="eyebrow">{t('invitations.acceptEyebrow')}</p>
        {createdUsername ? (
          <>
            <h1 id="invitation-acceptance-heading">{t('invitations.ready')}</h1>
            <p className="login-panel__description">{t('invitations.readyHelp', { username: createdUsername })}</p>
            <button
              className="login-button icon-button invitation-acceptance__continue"
              type="button"
              onClick={onContinueToLogin}
            >
              <LoginIcon />
              {t('invitations.continue')}
            </button>
          </>
        ) : (
          <>
            <h1 id="invitation-acceptance-heading">{t('invitations.account')}</h1>
            <p className="login-panel__description">{t('invitations.accountHelp')}</p>
            <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
              <label htmlFor={passwordId}>{t('invitations.password')}</label>
              <input
                id={passwordId}
                type="password"
                value={password}
                minLength={MINIMUM_PASSWORD_LENGTH}
                maxLength={128}
                autoComplete="new-password"
                required
                onChange={(event) => setPassword(event.target.value)}
              />
              <label htmlFor={confirmationId}>{t('invitations.confirmPassword')}</label>
              <input
                id={confirmationId}
                type="password"
                value={confirmation}
                minLength={MINIMUM_PASSWORD_LENGTH}
                maxLength={128}
                autoComplete="new-password"
                required
                onChange={(event) => setConfirmation(event.target.value)}
              />
              <button
                className="login-button icon-button"
                type="submit"
                disabled={
                  submitting ||
                  password.length < MINIMUM_PASSWORD_LENGTH ||
                  confirmation.length < MINIMUM_PASSWORD_LENGTH
                }
              >
                <CheckIcon />
                {t(submitting ? 'invitations.creatingAccount' : 'invitations.account')}
              </button>
            </form>
            {error && (
              <p className="login-error" role="alert">
                {error}
              </p>
            )}
            <button className="invitation-acceptance__back" type="button" onClick={onContinueToLogin}>
              {t('invitations.back')}
            </button>
          </>
        )}
      </section>
    </main>
  )
}
