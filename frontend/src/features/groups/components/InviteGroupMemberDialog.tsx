import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { DialogActions } from '../../../shared/ui/DialogActions'
import { GroupAddIcon } from '../../../shared/ui/icons'
import type { GroupMemberCandidate, GroupRole } from '../api'

interface InviteGroupMemberDialogProps {
  submitting: boolean
  loadingCandidates: boolean
  candidates: GroupMemberCandidate[]
  error: string | null
  onSubmit: (userId: string, role: GroupRole) => Promise<void>
  onClose: () => void
}

export function InviteGroupMemberDialog({
  submitting,
  loadingCandidates,
  candidates,
  error,
  onSubmit,
  onClose,
}: InviteGroupMemberDialogProps) {
  const { t } = useTranslation()
  const headingId = useId()
  const userSelectId = useId()
  const roleId = useId()
  const [selectedUserId, setSelectedUserId] = useState('')
  const [role, setRole] = useState<GroupRole>('member')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !selectedUserId) return
    await onSubmit(selectedUserId, role)
  }

  return (
    <Dialog titleId={headingId} className="group-form-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t('groups.addMember')}</h2>
        <p>{t('groups.candidateHelp')}</p>
      </div>
      <form className="group-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={userSelectId}>{t('groups.user')}</label>
        <select
          className="form-control form-control--subtle"
          id={userSelectId}
          value={selectedUserId}
          required
          autoFocus
          disabled={loadingCandidates || candidates.length === 0}
          onChange={(event) => setSelectedUserId(event.target.value)}
        >
          <option value="">{loadingCandidates ? t('common.loading') : t('groups.selectUser')}</option>
          {candidates.map((candidate) => (
            <option key={candidate.user_id} value={candidate.user_id}>
              {candidate.username}
            </option>
          ))}
        </select>
        {!loadingCandidates && candidates.length === 0 && !error && (
          <p className="group-form__hint">{t('groups.noCandidates')}</p>
        )}
        <label htmlFor={roleId}>{t('groups.role')}</label>
        <select
          className="form-control form-control--subtle"
          id={roleId}
          value={role}
          onChange={(event) => setRole(event.target.value as GroupRole)}
        >
          <option value="member">{t('common.member')}</option>
          <option value="admin">{t('common.admin')}</option>
        </select>
        {error && (
          <p className="dialog-error" role="alert">
            {error}
          </p>
        )}
        <DialogActions disabled={submitting} onCancel={onClose}>
          <button className="primary-button icon-button" type="submit" disabled={submitting || !selectedUserId}>
            <GroupAddIcon />
            {submitting ? t('groups.adding') : t('groups.add')}
          </button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
