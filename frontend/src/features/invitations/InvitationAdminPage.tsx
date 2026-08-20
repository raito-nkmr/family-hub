import { useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../shared/lib/format'
import { EmptyState } from '../../shared/ui/EmptyState'
import { LoadingState } from '../../shared/ui/LoadingState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { CancelIcon, CloseIcon, ContentCopyIcon, DeleteIcon, PersonAddIcon } from '../../shared/ui/icons'
import type { InvitationExpiryHours } from './api'
import { copyTextToClipboard } from './clipboard'
import { useInvitations } from './useInvitations'

interface InvitationAdminPageProps {
  onUnauthorized: () => void
}

function buildInvitationUrl(token: string): string {
  return `${window.location.origin}${window.location.pathname}#invite=${encodeURIComponent(token)}`
}

export function InvitationAdminPage({ onUnauthorized }: InvitationAdminPageProps) {
  const { t } = useTranslation()
  const usernameId = useId()
  const expiryId = useId()
  const [username, setUsername] = useState('')
  const [expiresInHours, setExpiresInHours] = useState<InvitationExpiryHours>(24)
  const invitationUrlInputRef = useRef<HTMLInputElement>(null)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle')
  const state = useInvitations({ onUnauthorized })
  const invitationUrl = state.createdInvitation ? buildInvitationUrl(state.createdInvitation.token) : null
  const pendingInvitations = state.invitations.filter((invitation) => invitation.status === 'pending')
  const pastInvitations = state.invitations.filter((invitation) => invitation.status !== 'pending')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!username.trim() || state.submitting) return
    await state.create(username.trim(), expiresInHours)
    setCopyStatus('idle')
  }

  const copyInvitationUrl = async () => {
    if (!invitationUrl || !invitationUrlInputRef.current) return
    const copied = await copyTextToClipboard(invitationUrl, invitationUrlInputRef.current)
    setCopyStatus(copied ? 'copied' : 'failed')
  }

  return (
    <main id="top" className="invitation-page">
      <section className="invitation-hero">
        <div>
          <h1>{t('invitations.title')}</h1>
          <p>{t('invitations.description')}</p>
        </div>
      </section>

      <section className="invitation-create" aria-labelledby="invitation-create-heading">
        <div>
          <h2 id="invitation-create-heading">{t('invitations.create')}</h2>
        </div>
        <form className="invitation-create__form" onSubmit={(event) => void handleSubmit(event)}>
          <div className="invitation-create__fields">
            <label htmlFor={usernameId}>
              <span>{t('invitations.username')}</span>
              <input
                className="form-control"
                id={usernameId}
                value={username}
                minLength={1}
                maxLength={64}
                autoCapitalize="none"
                spellCheck={false}
                placeholder={t('invitations.usernamePlaceholder')}
                required
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            <label htmlFor={expiryId}>
              <span>{t('invitations.expiry')}</span>
              <select
                className="form-control"
                id={expiryId}
                value={expiresInHours}
                onChange={(event) => setExpiresInHours(Number(event.target.value) as InvitationExpiryHours)}
              >
                <option value={24}>{t('invitations.expiryOneDay')}</option>
                <option value={72}>{t('invitations.expiryThreeDays')}</option>
                <option value={168}>{t('invitations.expirySevenDays')}</option>
              </select>
            </label>
          </div>
          <div className="invitation-create__action">
            <button
              className="primary-button icon-button"
              type="submit"
              disabled={state.submitting || !username.trim()}
            >
              <PersonAddIcon />
              {t(state.submitting ? 'invitations.issuing' : 'invitations.issue')}
            </button>
          </div>
        </form>

        {invitationUrl && (
          <div className="invitation-result" role="status">
            <strong>{t('invitations.result', { username: state.createdInvitation?.username })}</strong>
            <p>{t('invitations.resultHelp')}</p>
            <div>
              <input
                ref={invitationUrlInputRef}
                className="form-control"
                value={invitationUrl}
                aria-label={t('invitations.urlLabel')}
                readOnly
                onFocus={(event) => event.target.select()}
              />
              <button className="secondary-button icon-button" type="button" onClick={() => void copyInvitationUrl()}>
                <ContentCopyIcon />
                {t(copyStatus === 'copied' ? 'invitations.copied' : 'invitations.copy')}
              </button>
            </div>
            {copyStatus === 'failed' && <PageMessage>{t('invitations.copyFailed')}</PageMessage>}
            <button
              className="invitation-result__close icon-button"
              type="button"
              onClick={state.clearCreatedInvitation}
            >
              <CloseIcon />
              {t('invitations.closeUrl')}
            </button>
          </div>
        )}
        {state.error && <PageMessage>{state.error}</PageMessage>}
      </section>

      <section className="invitation-library" aria-labelledby="invitation-list-heading">
        <div className="section-heading">
          <div>
            <h2 id="invitation-list-heading">{t('invitations.pendingTitle')}</h2>
            <p>{t('invitations.pendingHelp')}</p>
          </div>
          <RefreshButton onClick={state.refresh} disabled={state.loading} />
        </div>
        {state.loading ? (
          <LoadingState label={t('invitations.loading')} />
        ) : pendingInvitations.length > 0 ? (
          <div className="invitation-list">
            {pendingInvitations.map((invitation) => (
              <article className="invitation-card" key={invitation.id}>
                <div>
                  <strong>{invitation.username}</strong>
                  <span className="invitation-card__status invitation-card__status--pending">
                    {t('invitations.waitingForFamily')}
                  </span>
                </div>
                <p>{t('invitations.expires', { expires: formatDateTime(invitation.expires_at) })}</p>
                <button
                  className="danger-button"
                  type="button"
                  disabled={state.removingId === invitation.id}
                  onClick={() => void state.remove(invitation)}
                >
                  <CancelIcon />
                  {t('invitations.cancelAndRemove')}
                </button>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<PersonAddIcon />}
            title={t('invitations.noPending')}
            description={t('invitations.noPendingHelp')}
          />
        )}
        {pastInvitations.length > 0 && (
          <details className="invitation-past">
            <summary>{t('invitations.pastTitle', { count: pastInvitations.length })}</summary>
            <p>{t('invitations.pastHelp')}</p>
            <div className="invitation-list">
              {pastInvitations.map((invitation) => (
                <article className="invitation-card invitation-card--past" key={invitation.id}>
                  <div>
                    <strong>{invitation.username}</strong>
                    <span className={`invitation-card__status invitation-card__status--${invitation.status}`}>
                      {t(`invitations.status.${invitation.status}`)}
                    </span>
                  </div>
                  <p>{t('invitations.created', { created: formatDateTime(invitation.created_at) })}</p>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={state.removingId === invitation.id}
                    onClick={() => void state.remove(invitation)}
                  >
                    <DeleteIcon />
                    {t('invitations.removeFromHistory')}
                  </button>
                </article>
              ))}
            </div>
          </details>
        )}
      </section>
    </main>
  )
}
