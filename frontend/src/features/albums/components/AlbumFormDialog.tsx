import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Dialog } from '../../../shared/ui/Dialog'
import { DialogActions } from '../../../shared/ui/DialogActions'
import { AlbumIcon, SaveIcon } from '../../../shared/ui/icons'
import type { FamilyGroup } from '../../groups/api'
import type { Album } from '../api'

interface AlbumFormValue {
  title: string
  description: string | null
  group_ids: string[]
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
  const existingGroups = (album?.group_ids ?? []).map((id, index) => ({
    id,
    name: album?.group_names[index] ?? id,
  }))
  const availableGroups = [
    ...groups,
    ...existingGroups.filter((existing) => !groups.some((group) => group.id === existing.id)),
  ]
  const [groupIds, setGroupIds] = useState<string[]>(album?.group_ids ?? (groups[0]?.id ? [groups[0].id] : []))

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting || !title.trim() || groupIds.length === 0) return
    await onSubmit({ title: title.trim(), description: description.trim() || null, group_ids: groupIds })
  }

  return (
    <Dialog titleId={headingId} className="album-form-dialog" busy={submitting} onClose={onClose}>
      <div className="dialog__heading">
        <h2 id={headingId}>{t(album ? 'albums.edit' : 'albums.create')}</h2>
      </div>
      <form className="album-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor={titleId}>{t('albums.name')}</label>
        <input
          className="form-control form-control--subtle"
          id={titleId}
          value={title}
          maxLength={120}
          required
          autoFocus
          placeholder={t('albums.namePlaceholder')}
          onChange={(event) => setTitle(event.target.value)}
        />
        <fieldset className="album-form__groups">
          <legend>{t('albums.groups')}</legend>
          {availableGroups.map((group) => (
            <label className="album-form__group-option" key={group.id}>
              <input
                type="checkbox"
                checked={groupIds.includes(group.id)}
                onChange={() =>
                  setGroupIds((current) =>
                    current.includes(group.id) ? current.filter((id) => id !== group.id) : [...current, group.id],
                  )
                }
              />
              {group.name}
            </label>
          ))}
        </fieldset>
        <p className="album-form__groups-help">{t('albums.groupsHelp')}</p>
        <label htmlFor={descriptionId}>{t('albums.optionalDescription')}</label>
        <textarea
          className="form-control form-control--subtle"
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
        <DialogActions disabled={submitting} onCancel={onClose}>
          <button
            className="primary-button icon-button"
            type="submit"
            disabled={submitting || !title.trim() || groupIds.length === 0}
          >
            {album ? <SaveIcon /> : <AlbumIcon />}
            {submitting ? t('common.saving') : album ? t('albums.saveChanges') : t('albums.create')}
          </button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
