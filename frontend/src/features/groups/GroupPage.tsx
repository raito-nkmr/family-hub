import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { formatDateTime } from '../../shared/lib/format'
import { EmptyState } from '../../shared/ui/EmptyState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { BackIcon, CheckIcon, DeleteIcon, GroupAddIcon, GroupIcon, PlusIcon, SaveIcon } from '../../shared/ui/icons'
import {
  decideGroupMembershipInvitation,
  getGroupAdministration,
  getGroupAuditEvents,
  getMyGroupMembershipInvitations,
  type GroupRole,
} from './api'
import { InviteGroupMemberDialog } from './components/InviteGroupMemberDialog'
import { GroupFormDialog } from './components/GroupFormDialog'
import { useGroups } from './useGroups'

interface GroupPageProps {
  currentUserId: string
  onUnauthorized: () => void
}

export function GroupPage({ currentUserId, onUnauthorized }: GroupPageProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [renameValue, setRenameValue] = useState('')
  const state = useGroups({ currentUserId, onUnauthorized })
  const selectedGroup = state.selectedGroup
  const invitationsQuery = useQuery({
    queryKey: queryKeys.groupMembershipInvitations,
    queryFn: ({ signal }) => getMyGroupMembershipInvitations(signal),
  })
  const invitationMutation = useMutation({
    mutationFn: ({ id, accept }: { id: string; accept: boolean }) => decideGroupMembershipInvitation(id, accept),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.groupMembershipInvitations }),
        queryClient.invalidateQueries({ queryKey: queryKeys.groups }),
      ])
    },
  })
  const administrationQuery = useQuery({
    queryKey: queryKeys.groupAdministration(selectedGroup?.id ?? ''),
    queryFn: ({ signal }) => getGroupAdministration(selectedGroup!.id, signal),
    enabled: selectedGroup?.current_user_role === 'admin',
  })
  const auditQuery = useQuery({
    queryKey: queryKeys.groupAudit(selectedGroup?.id ?? ''),
    queryFn: ({ signal }) => getGroupAuditEvents(selectedGroup!.id, signal),
    enabled: selectedGroup?.current_user_role === 'admin',
  })
  useUnauthorizedError(administrationQuery.error, onUnauthorized)
  useUnauthorizedError(auditQuery.error, onUnauthorized)
  useUnauthorizedError([invitationsQuery.error, invitationMutation.error].find(isUnauthorizedError), onUnauthorized)

  const submitRename = async (event: FormEvent) => {
    event.preventDefault()
    const name = renameValue.trim()
    if (!name) return
    if (await state.rename(name)) setRenameValue('')
  }

  if (selectedGroup) {
    return (
      <>
        <main id="top" className="group-detail-page">
          <button className="back-button" type="button" onClick={state.backToList}>
            <BackIcon />
            {t('groups.back')}
          </button>
          <header className="group-detail-header">
            <span className="group-detail-header__icon">
              <GroupIcon />
            </span>
            <div>
              <p className="eyebrow">{t('groups.detailEyebrow')}</p>
              <h1>{selectedGroup.name}</h1>
              <p>
                {t('groups.memberCount', { count: selectedGroup.member_count })} ·{' '}
                {t('groups.youAre', {
                  role: t(selectedGroup.current_user_role === 'admin' ? 'common.admin' : 'common.member'),
                })}
              </p>
            </div>
          </header>
          {selectedGroup.current_user_role === 'admin' && (
            <section className="group-members">
              <h2>{t('groups.administration')}</h2>
              <form className="group-form" onSubmit={(event) => void submitRename(event)}>
                <label>
                  {t('groups.rename')}
                  <input
                    className="form-control form-control--subtle"
                    value={renameValue}
                    maxLength={100}
                    placeholder={selectedGroup.name}
                    onChange={(event) => setRenameValue(event.target.value)}
                  />
                </label>
                <button
                  className="success-button icon-button"
                  type="submit"
                  disabled={!renameValue.trim() || state.submitting}
                >
                  <SaveIcon />
                  {t('common.save')}
                </button>
              </form>
              <GroupTimezoneForm
                key={`${selectedGroup.id}:${selectedGroup.timezone}`}
                timezone={selectedGroup.timezone}
                submitting={state.submitting}
                updateTimezone={state.updateTimezone}
              />
              {administrationQuery.error && !isUnauthorizedError(administrationQuery.error) && (
                <PageMessage>{t('groups.administrationLoadFailed')}</PageMessage>
              )}
              {administrationQuery.data && (
                <dl className="metadata-list">
                  <div>
                    <dt>{t('albums.title')}</dt>
                    <dd>{administrationQuery.data.album_count}</dd>
                  </div>
                  <div>
                    <dt>{t('photos.title')}</dt>
                    <dd>{administrationQuery.data.shared_photo_count}</dd>
                  </div>
                  <div>
                    <dt>{t('chores.title')}</dt>
                    <dd>{administrationQuery.data.chore_task_count}</dd>
                  </div>
                  <div>
                    <dt>{t('shopping.title')}</dt>
                    <dd>{administrationQuery.data.shopping_item_count}</dd>
                  </div>
                </dl>
              )}
              <h3>{t('groups.auditLog')}</h3>
              {auditQuery.error && !isUnauthorizedError(auditQuery.error) && (
                <PageMessage>{t('groups.auditLoadFailed')}</PageMessage>
              )}
              <ul className="maintenance-runs">
                {auditQuery.data?.slice(0, 20).map((event) => (
                  <li key={event.id}>
                    <span>
                      <strong>{t(`systemStatus.auditActions.${event.action.replaceAll('.', '_')}`)}</strong>
                      <small>
                        {event.actor_username} · {formatDateTime(event.created_at)}
                      </small>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className="group-members" aria-labelledby="group-members-heading">
            <div className="section-heading">
              <div>
                <h2 id="group-members-heading">{t('groups.members')}</h2>
              </div>
              {selectedGroup.current_user_role === 'admin' && (
                <button className="primary-button icon-button" type="button" onClick={() => state.openDialog('invite')}>
                  <GroupAddIcon />
                  {t('groups.inviteMember')}
                </button>
              )}
            </div>
            {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
            <div className="group-member-list">
              {selectedGroup.members.map((member) => {
                const isLastActiveGroupAdministrator =
                  administrationQuery.data !== undefined &&
                  member.is_active &&
                  member.role === 'admin' &&
                  administrationQuery.data.active_admin_count <= 1
                return (
                  <article className="group-member-card" key={member.user_id}>
                    <span className="group-member-card__avatar">{member.username.slice(0, 1).toUpperCase()}</span>
                    <div className="group-member-card__identity">
                      <strong>{member.username}</strong>
                      <span>{t(member.is_active ? 'groups.active' : 'groups.inactive')}</span>
                    </div>
                    <time dateTime={member.joined_at}>
                      {t('groups.joined', { date: formatDateTime(member.joined_at) })}
                    </time>
                    {selectedGroup.current_user_role === 'admin' ? (
                      <div className="group-member-card__actions">
                        <select
                          value={member.role}
                          aria-label={t('groups.roleLabel', { username: member.username })}
                          disabled={state.memberActionId !== null || isLastActiveGroupAdministrator}
                          title={isLastActiveGroupAdministrator ? t('errors.groupLastAdmin') : undefined}
                          onChange={(event) => void state.changeRole(member, event.target.value as GroupRole)}
                        >
                          <option value="member">{t('common.member')}</option>
                          <option value="admin">{t('common.admin')}</option>
                        </select>
                        <button
                          className="group-member-card__remove"
                          type="button"
                          aria-label={t('groups.removeLabel', { username: member.username })}
                          disabled={state.memberActionId !== null || isLastActiveGroupAdministrator}
                          title={isLastActiveGroupAdministrator ? t('errors.groupLastAdmin') : undefined}
                          onClick={() => void state.removeMember(member)}
                        >
                          <DeleteIcon />
                          {t('groups.remove')}
                        </button>
                      </div>
                    ) : (
                      <span className="group-member-card__role">
                        {t(member.role === 'admin' ? 'common.admin' : 'common.member')}
                      </span>
                    )}
                  </article>
                )
              })}
            </div>
          </section>
        </main>
        {state.showInviteMemberDialog && (
          <InviteGroupMemberDialog
            submitting={state.submitting}
            loadingCandidates={state.loadingMemberCandidates}
            candidates={state.memberCandidates}
            error={state.dialogError}
            onSubmit={state.inviteMember}
            onClose={state.closeInviteMemberDialog}
          />
        )}
      </>
    )
  }

  return (
    <>
      <main id="top" className="group-page">
        <section className="group-hero">
          <div>
            <h1>{t('groups.title')}</h1>
            <p>{t('groups.description')}</p>
          </div>
          <button className="primary-button icon-button" type="button" onClick={() => state.openDialog('create')}>
            <PlusIcon />
            {t('groups.create')}
          </button>
        </section>
        {invitationsQuery.error && !isUnauthorizedError(invitationsQuery.error) && (
          <PageMessage>{t('errors.invitationLoad')}</PageMessage>
        )}
        {invitationMutation.error && !isUnauthorizedError(invitationMutation.error) && (
          <PageMessage>{t('errors.invitationDecision')}</PageMessage>
        )}
        {(invitationsQuery.data?.length ?? 0) > 0 && (
          <section className="group-library">
            <h2>{t('groups.pendingInvitations')}</h2>
            <div className="group-grid">
              {invitationsQuery.data?.map((invitation) => (
                <article className="group-card" key={invitation.id}>
                  <span className="group-card__body">
                    <strong>{invitation.group_name}</strong>
                    <span>{t(invitation.role === 'admin' ? 'common.admin' : 'common.member')}</span>
                    <span>
                      <button
                        className="success-button icon-button"
                        type="button"
                        disabled={invitationMutation.isPending}
                        onClick={() => invitationMutation.mutate({ id: invitation.id, accept: true })}
                      >
                        <CheckIcon />
                        {t('common.accept')}
                      </button>
                      <button
                        className="danger-button icon-button"
                        type="button"
                        disabled={invitationMutation.isPending}
                        onClick={() => invitationMutation.mutate({ id: invitation.id, accept: false })}
                      >
                        <DeleteIcon />
                        {t('common.reject')}
                      </button>
                    </span>
                  </span>
                </article>
              ))}
            </div>
          </section>
        )}
        <section className="group-library" aria-labelledby="group-library-heading">
          <div className="section-heading">
            <div>
              <h2 id="group-library-heading">{t('groups.list')}</h2>
              <p>
                {state.groups.length > 0 ? t('groups.count', { count: state.groups.length }) : t('groups.emptySummary')}
              </p>
            </div>
            <RefreshButton onClick={state.refresh} disabled={state.loading} />
          </div>
          {state.pageError && <PageMessage>{state.pageError}</PageMessage>}
          {state.loading ? (
            <div className="group-grid" aria-label={t('groups.loading')}>
              {Array.from({ length: 2 }, (_, index) => (
                <div className="album-skeleton" key={index} />
              ))}
            </div>
          ) : state.groups.length > 0 ? (
            <div className="group-grid">
              {state.groups.map((group) => (
                <button className="group-card" type="button" key={group.id} onClick={() => void state.openGroup(group)}>
                  <span className="group-card__icon">
                    <GroupIcon />
                  </span>
                  <span className="group-card__body">
                    <strong>{group.name}</strong>
                    <span>{t('groups.memberCount', { count: group.member_count })}</span>
                    <small>{t(group.current_user_role === 'admin' ? 'common.admin' : 'common.member')}</small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              className="group-empty-state"
              icon={<GroupIcon />}
              title={t('groups.empty')}
              description={t('groups.emptyHelp')}
              titleAs="strong"
            />
          )}
        </section>
      </main>
      {state.showCreateDialog && (
        <GroupFormDialog
          submitting={state.submitting}
          error={state.dialogError}
          onSubmit={state.create}
          onClose={state.closeCreateDialog}
        />
      )}
    </>
  )
}

function GroupTimezoneForm({
  timezone,
  submitting,
  updateTimezone,
}: {
  timezone: string
  submitting: boolean
  updateTimezone: (timezone: string) => Promise<boolean>
}) {
  const { t } = useTranslation()
  const [value, setValue] = useState(timezone)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await updateTimezone(value)
  }

  return (
    <form className="group-form" onSubmit={(event) => void submit(event)}>
      <label>
        {t('groups.timezone')}
        <select
          className="form-control form-control--subtle"
          value={value}
          disabled={submitting}
          onChange={(event) => setValue(event.target.value)}
        >
          {TIMEZONE_OPTIONS.map((option) => (
            <option value={option} key={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <button className="success-button icon-button" type="submit" disabled={value === timezone || submitting}>
        <SaveIcon />
        {t('common.save')}
      </button>
    </form>
  )
}

const TIMEZONE_OPTIONS = [
  'Asia/Tokyo',
  'Australia/Sydney',
  'Europe/Berlin',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'UTC',
]
