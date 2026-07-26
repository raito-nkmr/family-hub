import { useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDateTime } from '../../shared/lib/format'
import { CancelIcon, CloseIcon, ContentCopyIcon, DeleteIcon, PersonAddIcon, RefreshIcon } from '../../shared/ui/icons'
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
  const [expiresInHours, setExpiresInHours] = useState(24)
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
                id={expiryId}
                value={expiresInHours}
                onChange={(event) => setExpiresInHours(Number(event.target.value))}
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
            {copyStatus === 'failed' && (
              <p className="page-message page-message--error" role="alert">
                {t('invitations.copyFailed')}
              </p>
            )}
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
        {state.error && (
          <div className="page-message page-message--error" role="alert">
            {state.error}
          </div>
        )}
      </section>

      <section className="invitation-library" aria-labelledby="invitation-list-heading">
        <div className="section-heading">
          <div>
            <h2 id="invitation-list-heading">{t('invitations.pendingTitle')}</h2>
            <p>{t('invitations.pendingHelp')}</p>
          </div>
          <button
            className="refresh-button"
            type="button"
            disabled={state.loading}
            onClick={() => void state.refresh()}
          >
            <RefreshIcon />
            <span>{t('common.refresh')}</span>
          </button>
        </div>
        {state.loading ? (
          <div className="feature-loading" aria-label={t('invitations.loading')}>
            <span className="spinner" />
          </div>
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
          <div className="empty-state">
            <PersonAddIcon />
            <h3>{t('invitations.noPending')}</h3>
            <p>{t('invitations.noPendingHelp')}</p>
          </div>
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
