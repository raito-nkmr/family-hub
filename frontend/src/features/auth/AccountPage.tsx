import { useId, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { isUnauthorizedError } from '../../shared/api/errors'
import { ApiError } from '../../shared/api/client'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { formatDateTime } from '../../shared/lib/format'
import { LoadingState } from '../../shared/ui/LoadingState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { DeleteIcon, LogoutIcon, SaveIcon } from '../../shared/ui/icons'
import { NotificationSettings } from '../notifications/NotificationSettings'
import { PwaInstallCard } from '../pwa/PwaInstallCard'
import { changePassword, getSessions, logoutAll, revokeSession, type AuthUserSession } from './api'

interface AccountPageProps {
  username: string
  onSessionEnded: () => void
  showPwaInstallGuideEntry: boolean
  onShowPwaInstallGuide: () => void
}

export function AccountPage({
  username,
  onSessionEnded,
  showPwaInstallGuideEntry,
  onShowPwaInstallGuide,
}: AccountPageProps) {
  const { t } = useTranslation()
  const currentPasswordId = useId()
  const newPasswordId = useId()
  const confirmationId = useId()
  const queryClient = useQueryClient()
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const sessionsQuery = useQuery({
    queryKey: queryKeys.sessions,
    queryFn: ({ signal }) => getSessions(signal),
  })
  const revokeMutation = useMutation({ mutationFn: revokeSession })
  const logoutAllMutation = useMutation({ mutationFn: logoutAll })
  const passwordMutation = useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) => changePassword(current, next),
  })
  const unauthorizedError = [
    sessionsQuery.error,
    revokeMutation.error,
    logoutAllMutation.error,
    passwordMutation.error,
  ].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedError, onSessionEnded)
  const sessions: AuthUserSession[] = sessionsQuery.data?.items ?? []
  const busySessionId = revokeMutation.isPending ? revokeMutation.variables : logoutAllMutation.isPending ? 'all' : null
  const changingPassword = passwordMutation.isPending
  const displayedSessionError =
    sessionError ??
    (sessionsQuery.error && !isUnauthorizedError(sessionsQuery.error) ? t('account.sessionsLoadFailed') : null)

  const submitPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (newPassword !== confirmation) {
      setPasswordError(t('account.passwordMismatch'))
      return
    }
    setPasswordError(null)
    try {
      await passwordMutation.mutateAsync({ current: currentPassword, next: newPassword })
      onSessionEnded()
    } catch (error) {
      if (isUnauthorizedError(error)) onSessionEnded()
      else if (error instanceof ApiError && error.status === 400) setPasswordError(t('account.currentIncorrect'))
      else setPasswordError(t('account.passwordChangeFailed'))
    }
  }

  const removeSession = async (sessionId: string) => {
    setSessionError(null)
    try {
      await revokeMutation.mutateAsync(sessionId)
      queryClient.setQueryData(queryKeys.sessions, {
        ...sessionsQuery.data,
        items: sessions.filter((session) => session.id !== sessionId),
      })
    } catch (error) {
      if (isUnauthorizedError(error)) onSessionEnded()
      else setSessionError(t('account.sessionRevokeFailed'))
    }
  }

  const endAllSessions = async () => {
    setSessionError(null)
    try {
      await logoutAllMutation.mutateAsync()
      onSessionEnded()
    } catch (error) {
      if (isUnauthorizedError(error)) onSessionEnded()
      else setSessionError(t('account.logoutAllFailed'))
    }
  }

  return (
    <main id="top" className="account-page">
      <header className="account-hero">
        <h1>{t('account.title')}</h1>
        <p>{t('account.description', { username })}</p>
      </header>

      <div className="account-grid">
        {showPwaInstallGuideEntry && <PwaInstallCard variant="account" onShowInstallGuide={onShowPwaInstallGuide} />}
        <NotificationSettings
          showInstallGuide={showPwaInstallGuideEntry}
          onShowInstallGuide={onShowPwaInstallGuide}
          onUnauthorized={onSessionEnded}
        />
        <section className="account-panel" aria-labelledby="password-heading">
          <h2 id="password-heading">{t('account.passwordTitle')}</h2>
          <p>{t('account.passwordHelp')}</p>
          <form className="account-form" onSubmit={(event) => void submitPassword(event)}>
            <label htmlFor={currentPasswordId}>{t('account.currentPassword')}</label>
            <input
              className="form-control"
              id={currentPasswordId}
              type="password"
              value={currentPassword}
              autoComplete="current-password"
              maxLength={128}
              required
              disabled={changingPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
            <label htmlFor={newPasswordId}>{t('account.newPassword')}</label>
            <input
              className="form-control"
              id={newPasswordId}
              type="password"
              value={newPassword}
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
              disabled={changingPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <label htmlFor={confirmationId}>{t('account.confirmPassword')}</label>
            <input
              className="form-control"
              id={confirmationId}
              type="password"
              value={confirmation}
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
              disabled={changingPassword}
              onChange={(event) => setConfirmation(event.target.value)}
            />
            {passwordError && <PageMessage>{passwordError}</PageMessage>}
            <button className="success-button icon-button" type="submit" disabled={changingPassword}>
              <SaveIcon />
              {t(changingPassword ? 'account.changingPassword' : 'account.changePassword')}
            </button>
          </form>
        </section>

        <section className="account-panel" aria-labelledby="sessions-heading">
          <div className="account-panel__heading">
            <div>
              <h2 id="sessions-heading">{t('account.sessionsTitle')}</h2>
              <p>{t('account.sessionsHelp')}</p>
            </div>
            <RefreshButton onClick={() => sessionsQuery.refetch()} disabled={sessionsQuery.isFetching} />
          </div>
          {displayedSessionError && <PageMessage>{displayedSessionError}</PageMessage>}
          {sessionsQuery.isPending ? (
            <LoadingState label={t('account.loadingSessions')} />
          ) : (
            <ul className="session-list">
              {sessions.map((session) => (
                <li key={session.id}>
                  <div>
                    <strong>{session.current ? t('account.currentSession') : t('account.otherSession')}</strong>
                    <small>{t('account.lastUsed', { date: formatDateTime(session.last_used_at) })}</small>
                    <small>{t('account.expires', { date: formatDateTime(session.expires_at) })}</small>
                  </div>
                  {!session.current && (
                    <button
                      className="danger-button icon-button"
                      type="button"
                      disabled={busySessionId !== null}
                      onClick={() => void removeSession(session.id)}
                    >
                      <DeleteIcon />
                      {t(busySessionId === session.id ? 'account.revokingSession' : 'account.revokeSession')}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <button
            className="danger-button icon-button account-panel__logout-all"
            type="button"
            disabled={busySessionId !== null}
            onClick={() => void endAllSessions()}
          >
            <LogoutIcon />
            {t(busySessionId === 'all' ? 'account.loggingOutAll' : 'account.logoutAll')}
          </button>
        </section>
      </div>
    </main>
  )
}
