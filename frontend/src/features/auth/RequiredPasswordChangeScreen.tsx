import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../../shared/api/client'
import { isUnauthorizedError } from '../../shared/api/errors'
import type { Theme } from '../../shared/types/theme'
import { PublicAuthLayout } from '../../shared/ui/PublicAuthLayout'
import { CheckIcon, LogoutIcon } from '../../shared/ui/icons'
import { changePassword, logout } from './api'

interface RequiredPasswordChangeScreenProps {
  username: string
  theme: Theme
  onSessionEnded: () => void
  onToggleTheme: () => void
}

export function RequiredPasswordChangeScreen({
  username,
  theme,
  onSessionEnded,
  onToggleTheme,
}: RequiredPasswordChangeScreenProps) {
  const { t } = useTranslation()
  const currentPasswordId = useId()
  const newPasswordId = useId()
  const confirmationId = useId()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || loggingOut) return
    if (newPassword !== confirmation) {
      setError(t('auth.passwordMismatch'))
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await changePassword(currentPassword, newPassword)
      onSessionEnded()
    } catch (caught) {
      if (isUnauthorizedError(caught)) onSessionEnded()
      else if (caught instanceof ApiError && caught.status === 400) setError(t('auth.currentIncorrect'))
      else setError(t('auth.passwordChangeFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const signOut = async () => {
    if (submitting || loggingOut) return
    setLoggingOut(true)
    setError(null)
    try {
      await logout()
      onSessionEnded()
    } catch (caught) {
      if (isUnauthorizedError(caught)) onSessionEnded()
      else setError(t('auth.logoutFailed'))
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <PublicAuthLayout
      theme={theme}
      onToggleTheme={onToggleTheme}
      icon={<CheckIcon />}
      eyebrow={t('auth.eyebrow')}
      title={t('auth.mustChangeTitle')}
      titleId="required-password-change-heading"
      description={t('auth.mustChangeDescription', { username })}
    >
      <form className="login-form" onSubmit={(event) => void submit(event)}>
        <label htmlFor={currentPasswordId}>{t('auth.currentPassword')}</label>
        <input
          id={currentPasswordId}
          type="password"
          value={currentPassword}
          autoComplete="current-password"
          required
          disabled={submitting || loggingOut}
          onChange={(event) => setCurrentPassword(event.target.value)}
        />
        <label htmlFor={newPasswordId}>{t('auth.newPassword')}</label>
        <input
          id={newPasswordId}
          type="password"
          value={newPassword}
          minLength={8}
          maxLength={128}
          autoComplete="new-password"
          required
          disabled={submitting || loggingOut}
          onChange={(event) => setNewPassword(event.target.value)}
        />
        <label htmlFor={confirmationId}>{t('auth.confirmPassword')}</label>
        <input
          id={confirmationId}
          type="password"
          value={confirmation}
          minLength={8}
          maxLength={128}
          autoComplete="new-password"
          required
          disabled={submitting || loggingOut}
          onChange={(event) => setConfirmation(event.target.value)}
        />
        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        <button className="login-button icon-button" type="submit" disabled={submitting || loggingOut}>
          <CheckIcon />
          {t(submitting ? 'auth.changingPassword' : 'auth.changePassword')}
        </button>
      </form>
      <button
        className="secondary-button icon-button"
        type="button"
        disabled={submitting || loggingOut}
        onClick={() => void signOut()}
      >
        <LogoutIcon />
        {t(loggingOut ? 'auth.loggingOut' : 'header.logout')}
      </button>
    </PublicAuthLayout>
  )
}
