import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { AlbumIcon, CancelIcon, SaveIcon } from '../../../shared/ui/icons'
import type { FamilyGroup } from '../../groups/api'
import type { Album } from '../api'

interface AlbumFormValue {
  title: string
  description: string | null
  group_id: string
}

interface AlbumFormDialogProps {
  album?: Album
  submitting: boolean
  error: string | null
  groups: FamilyGroup[]
  onSubmit: (value: AlbumFormValue) => Promise<void>
  onClose: () => void
}

export function AlbumFormDialog({ album, submitting, error, groups, onSubmit, onClose }: AlbumFormDialogProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const headingId = useId()
  const descriptionId = useId()
  const [title, setTitle] = useState(album?.title ?? '')
  const [description, setDescription] = useState(album?.description ?? '')
  const [groupId, setGroupId] = useState(album?.group_id ?? groups[0]?.id ?? '')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !title.trim() || !groupId) return
    await onSubmit({ title: title.trim(), description: description.trim() || null, group_id: groupId })
  }

  return (
    <Dialog titleId={headingId} className="album-form-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t(album ? 'albums.edit' : 'albums.create')}</h2>
      </div>
      <form className="album-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={titleId}>{t('albums.name')}</label>
        <input
          id={titleId}
          value={title}
          maxLength={120}
          required
          autoFocus
          placeholder={t('albums.namePlaceholder')}
          onChange={(event) => setTitle(event.target.value)}
        />
        {!album && (
          <>
            <label htmlFor={`${titleId}-group`}>{t('albums.group')}</label>
            <select
              id={`${titleId}-group`}
              value={groupId}
              required
              onChange={(event) => setGroupId(event.target.value)}
            >
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
          </>
        )}
        <label htmlFor={descriptionId}>{t('albums.optionalDescription')}</label>
        <textarea
          id={descriptionId}
          value={description}
          maxLength={2000}
          rows={4}
          placeholder={t('albums.descriptionPlaceholder')}
          onChange={(event) => setDescription(event.target.value)}
        />
        {error && (
          <p className="dialog-error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-actions">
          <button
            className="danger-button danger-button--filled icon-button"
            type="button"
            onClick={onClose}
            disabled={submitting}
          >
            <CancelIcon />
            {t('common.cancel')}
          </button>
          <button
            className="primary-button icon-button"
            type="submit"
            disabled={submitting || !title.trim() || !groupId}
          >
            {album ? <SaveIcon /> : <AlbumIcon />}
            {submitting ? t('common.saving') : album ? t('albums.saveChanges') : t('albums.create')}
          </button>
        </div>
      </form>
    </Dialog>
  )
}
