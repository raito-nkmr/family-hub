import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { CancelIcon, ShareIcon } from '../../../shared/ui/icons'
import type { FamilyGroup } from '../../groups/api'

interface BulkPhotoSharingDialogProps {
  photoCount: number
  groups: FamilyGroup[]
  busy: boolean
  error: string | null
  onSubmit: (groupIds: string[]) => void
  onClose: () => void
}

export function BulkPhotoSharingDialog({
  photoCount,
  groups,
  busy,
  error,
  onSubmit,
  onClose,
}: BulkPhotoSharingDialogProps) {
  const { t } = useTranslation()
  const [groupIds, setGroupIds] = useState<string[]>([])

  return (
    <Dialog
      titleId="bulk-photo-sharing-title"
      className="bulk-photo-sharing"
      size="compact"
      busy={busy}
      onClose={onClose}
    >
      <div className="bulk-photo-sharing__heading">
        <h2 id="bulk-photo-sharing-title">{t('bulkPhotoSharing.title', { count: photoCount })}</h2>
        <p>{t('bulkPhotoSharing.description')}</p>
      </div>

      <fieldset className="bulk-photo-sharing__groups" disabled={busy}>
        <legend>{t('bulkPhotoSharing.groups')}</legend>
        {groups.length > 0 ? (
          groups.map((group) => (
            <label key={group.id}>
              <input
                type="checkbox"
                checked={groupIds.includes(group.id)}
                onChange={() =>
                  setGroupIds((current) =>
                    current.includes(group.id) ? current.filter((id) => id !== group.id) : [...current, group.id],
                  )
                }
              />
              <span>{group.name}</span>
            </label>
          ))
        ) : (
          <p>{t('bulkPhotoSharing.noGroups')}</p>
        )}
      </fieldset>

      {error && (
        <p className="form-message form-message--error" role="alert">
          {error}
        </p>
      )}

      <div className="bulk-photo-sharing__actions">
        <button
          type="button"
          className="danger-button danger-button--filled icon-button"
          onClick={onClose}
          disabled={busy}
        >
          <CancelIcon />
          {t('common.cancel')}
        </button>
        <button
          type="button"
          className="primary-button icon-button"
          onClick={() => onSubmit(groupIds)}
          disabled={busy || groupIds.length === 0}
        >
          <ShareIcon />
          {busy ? t('bulkPhotoSharing.saving') : t('bulkPhotoSharing.submit')}
        </button>
      </div>
    </Dialog>
  )
}
