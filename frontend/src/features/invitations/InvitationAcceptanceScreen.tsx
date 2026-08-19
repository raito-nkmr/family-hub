import { useId, useState, type FormEvent } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../../shared/api/client'
import type { Theme } from '../../shared/types/theme'
import { PublicAuthLayout } from '../../shared/ui/PublicAuthLayout'
import { CheckIcon, LoginIcon, PersonAddIcon } from '../../shared/ui/icons'
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
    <PublicAuthLayout
      theme={theme}
      onToggleTheme={onToggleTheme}
      icon={<PersonAddIcon />}
      eyebrow={t('invitations.acceptEyebrow')}
      title={t(createdUsername ? 'invitations.ready' : 'invitations.account')}
      titleId="invitation-acceptance-heading"
      description={t(createdUsername ? 'invitations.readyHelp' : 'invitations.accountHelp', {
        username: createdUsername ?? undefined,
      })}
      panelClassName="invitation-acceptance"
    >
      {createdUsername ? (
        <>
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
                submitting || password.length < MINIMUM_PASSWORD_LENGTH || confirmation.length < MINIMUM_PASSWORD_LENGTH
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
    </PublicAuthLayout>
  )
}
