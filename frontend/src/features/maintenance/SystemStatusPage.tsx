import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import { formatBytes, formatDateTime } from '../../shared/lib/format'
import { LoadingState } from '../../shared/ui/LoadingState'
import { PageMessage } from '../../shared/ui/PageMessage'
import { RefreshButton } from '../../shared/ui/RefreshButton'
import { AddModeratorIcon, BlockIcon, CheckIcon, RemoveModeratorIcon, SaveIcon } from '../../shared/ui/icons'
import {
  assignAdministrativeGroupAdministrator,
  getAdministrationSnapshot,
  getSystemStatus,
  updateAdministrativeUserRole,
  updateAdministrativeUserStatus,
} from './api'

interface SystemStatusPageProps {
  onUnauthorized: () => void
}

export function SystemStatusPage({ onUnauthorized }: SystemStatusPageProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [currentPassword, setCurrentPassword] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [recoveryUsers, setRecoveryUsers] = useState<Record<string, string>>({})
  const statusQuery = useQuery({
    queryKey: queryKeys.maintenanceStatus,
    queryFn: ({ signal }) => getSystemStatus(signal),
  })
  useUnauthorizedError(statusQuery.error, onUnauthorized)
  const administrationQuery = useQuery({
    queryKey: queryKeys.administration,
    queryFn: ({ signal }) => getAdministrationSnapshot(signal),
  })
  useUnauthorizedError(administrationQuery.error, onUnauthorized)
  const userMutation = useMutation({
    mutationFn: async (
      action:
        | { type: 'status'; userId: string; isActive: boolean }
        | { type: 'role'; userId: string; role: 'admin' | 'user' }
        | { type: 'group-admin'; groupId: string; userId: string },
    ) => {
      if (!currentPassword) throw new Error('password-required')
      if (action.type === 'status')
        return updateAdministrativeUserStatus(action.userId, action.isActive, currentPassword)
      if (action.type === 'group-admin')
        return assignAdministrativeGroupAdministrator(action.groupId, action.userId, currentPassword)
      return updateAdministrativeUserRole(action.userId, action.role, currentPassword)
    },
    onSuccess: async () => {
      setActionError(null)
      setCurrentPassword('')
      await queryClient.invalidateQueries({ queryKey: queryKeys.administration })
    },
    onError: () => setActionError(t('systemStatus.adminActionFailed')),
  })
  const status = statusQuery.data

  return (
    <main className="maintenance-page">
      <header className="page-heading">
        <div>
          <h1>{t('systemStatus.title')}</h1>
          <p>{t('systemStatus.description')}</p>
        </div>
        <RefreshButton
          disabled={statusQuery.isFetching}
          onClick={() => Promise.all([statusQuery.refetch(), administrationQuery.refetch()])}
        />
      </header>
      {statusQuery.error && !isUnauthorizedError(statusQuery.error) && (
        <PageMessage>{t('systemStatus.loadFailed')}</PageMessage>
      )}
      {status?.alerts.map((alert) => (
        <PageMessage key={alert}>{t(`systemStatus.alerts.${alert}`)}</PageMessage>
      ))}
      {statusQuery.isPending ? (
        <LoadingState label={t('systemStatus.loading')} />
      ) : status ? (
        <div className="maintenance-grid">
          <section className="maintenance-card maintenance-card--wide">
            <h2>{t('systemStatus.primaryStorage')}</h2>
            <dl className="maintenance-metadata-list">
              <div>
                <dt>{t('systemStatus.state')}</dt>
                <dd>{t(`storage.${status.storage.status}`)}</dd>
              </div>
              <div>
                <dt>{t('systemStatus.capacity')}</dt>
                <dd>
                  {status.storage.free_bytes === null || status.storage.total_bytes === null
                    ? t('common.unknown')
                    : t('systemStatus.capacityValue', {
                        free: formatBytes(status.storage.free_bytes),
                        total: formatBytes(status.storage.total_bytes),
                      })}
                </dd>
              </div>
              <div>
                <dt>{t('systemStatus.activePhotos')}</dt>
                <dd>
                  {t('systemStatus.photoTotal', {
                    count: status.storage.active_photo_count,
                    size: formatBytes(status.storage.active_photo_bytes),
                  })}
                </dd>
              </div>
              <div>
                <dt>{t('systemStatus.trashedPhotos')}</dt>
                <dd>
                  {t('systemStatus.photoTotal', {
                    count: status.storage.trashed_photo_count,
                    size: formatBytes(status.storage.trashed_photo_bytes),
                  })}
                </dd>
              </div>
            </dl>
          </section>
          <section className="maintenance-card maintenance-card--wide">
            <h2>{t('systemStatus.maintenance')}</h2>
            {status.latest_runs.length === 0 ? (
              <p>{t('systemStatus.noRuns')}</p>
            ) : (
              <ul className="maintenance-runs">
                {status.latest_runs.map((run) => (
                  <li key={run.id}>
                    <SaveIcon />
                    <span>
                      <strong>{t(`systemStatus.jobs.${run.job_type}`)}</strong>
                      <small>
                        {t(`systemStatus.statuses.${run.status}`)} · {formatDateTime(run.finished_at ?? run.started_at)}
                      </small>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="maintenance-card maintenance-card--wide">
            <h2>{t('systemStatus.userManagement')}</h2>
            <label className="maintenance-password">
              <span>{t('systemStatus.currentPassword')}</span>
              <input
                type="password"
                value={currentPassword}
                autoComplete="current-password"
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </label>
            {actionError && <PageMessage>{actionError}</PageMessage>}
            <div className="maintenance-table-wrap">
              <table className="maintenance-table">
                <thead>
                  <tr>
                    <th>{t('invitations.username')}</th>
                    <th>{t('systemStatus.state')}</th>
                    <th>{t('systemStatus.role')}</th>
                    <th>{t('systemStatus.groups')}</th>
                    <th>{t('systemStatus.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {administrationQuery.data?.users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.username}</td>
                      <td>{t(user.is_active ? 'systemStatus.active' : 'systemStatus.inactive')}</td>
                      <td>{t(`systemStatus.systemRoles.${user.system_role}`)}</td>
                      <td>{user.group_names.join(', ') || '—'}</td>
                      <td>
                        <button
                          type="button"
                          className={user.is_active ? 'danger-button icon-button' : 'success-button icon-button'}
                          disabled={userMutation.isPending || !currentPassword}
                          onClick={() =>
                            userMutation.mutate({ type: 'status', userId: user.id, isActive: !user.is_active })
                          }
                        >
                          {user.is_active ? <BlockIcon /> : <CheckIcon />}
                          {user.is_active ? t('systemStatus.deactivate') : t('systemStatus.activate')}
                        </button>
                        <button
                          type="button"
                          className="secondary-button icon-button"
                          disabled={userMutation.isPending || !currentPassword}
                          onClick={() =>
                            userMutation.mutate({
                              type: 'role',
                              userId: user.id,
                              role: user.system_role === 'admin' ? 'user' : 'admin',
                            })
                          }
                        >
                          {user.system_role === 'admin' ? <RemoveModeratorIcon /> : <AddModeratorIcon />}
                          {user.system_role === 'admin' ? t('systemStatus.demote') : t('systemStatus.promote')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="maintenance-card">
            <h2>{t('systemStatus.groupHealth')}</h2>
            <ul className="maintenance-runs">
              {administrationQuery.data?.groups.map((group) => (
                <li key={group.id}>
                  <span>
                    <strong>{group.name}</strong>
                    <small>
                      {t('systemStatus.groupHealthSummary', {
                        members: group.member_count,
                        admins: group.active_admin_count,
                      })}
                    </small>
                    <select
                      aria-label={t('systemStatus.recoveryUser')}
                      value={recoveryUsers[group.id] ?? ''}
                      onChange={(event) =>
                        setRecoveryUsers((current) => ({ ...current, [group.id]: event.target.value }))
                      }
                    >
                      <option value="">{t('groups.selectUser')}</option>
                      {administrationQuery.data.users
                        .filter((user) => user.is_active && user.group_names.includes(group.name))
                        .map((user) => (
                          <option value={user.id} key={user.id}>
                            {user.username}
                          </option>
                        ))}
                    </select>
                    <button
                      className="secondary-button icon-button"
                      type="button"
                      disabled={!currentPassword || !recoveryUsers[group.id] || userMutation.isPending}
                      onClick={() =>
                        userMutation.mutate({
                          type: 'group-admin',
                          groupId: group.id,
                          userId: recoveryUsers[group.id],
                        })
                      }
                    >
                      <AddModeratorIcon />
                      {t('systemStatus.assignGroupAdmin')}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </section>
          <section className="maintenance-card">
            <h2>{t('systemStatus.auditLog')}</h2>
            <ul className="maintenance-runs">
              {administrationQuery.data?.auditEvents.slice(0, 20).map((event) => (
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
          <section className="maintenance-card maintenance-card--wide">
            <h2>{t('systemStatus.history')}</h2>
            <ul className="maintenance-runs">
              {administrationQuery.data?.maintenanceHistory.map((run) => (
                <li key={run.id}>
                  <SaveIcon />
                  <span>
                    <strong>{t(`systemStatus.jobs.${run.job_type}`)}</strong>
                    <small>
                      {t(`systemStatus.statuses.${run.status}`)} · {formatDateTime(run.finished_at ?? run.started_at)}
                    </small>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      ) : null}
    </main>
  )
}
