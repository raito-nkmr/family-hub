import { useRef, useState, type FormEvent, type TouchEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatDateTime } from '../../../shared/lib/format'
import { Dialog } from '../../../shared/ui/Dialog'
import { useConfirmation } from '../../../shared/ui/confirmation'
import { DeleteIcon, FavoriteBorderIcon, FavoriteIcon, SaveIcon } from '../../../shared/ui/icons'
import type { FamilyGroup } from '../../groups/api'
import { getPhotoDownloadUrl, type Photo } from '../api'
import { formatPhotoContentType } from '../contentType'
import { PhotoPreview } from './PhotoPreview'

interface PhotoModalProps {
  photo: Photo
  currentUserId: string
  updatingMetadata: boolean
  error: string | null
  groups: FamilyGroup[]
  onClose: () => void
  onSharingChange: (groupIds: string[]) => void
  onToggleFavorite: () => void
  onMemoSave: (memo: string | null) => void
  onCaptureDateSave?: (capturedAt: string | null) => void
  onTrash: () => void
  onModerateGroupShare?: (groupId: string, currentPassword: string) => void
  onPreviousPhoto?: () => void
  onNextPhoto?: () => void
}

const SWIPE_THRESHOLD_PX = 50

export function PhotoModal({
  photo,
  currentUserId,
  updatingMetadata,
  error,
  groups,
  onClose,
  onSharingChange,
  onToggleFavorite,
  onMemoSave,
  onCaptureDateSave = () => {},
  onTrash,
  onModerateGroupShare,
  onPreviousPhoto,
  onNextPhoto,
}: PhotoModalProps) {
  const { t } = useTranslation()
  const confirm = useConfirmation()
  const isOwner = photo.uploaded_by_user_id === currentUserId
  const [memo, setMemo] = useState(photo.memo ?? '')
  const captureDateSource = photo.captured_at_override ?? photo.captured_at
  const [captureDateState, setCaptureDateState] = useState(() => ({
    photoId: photo.id,
    source: captureDateSource,
    value: toDateTimeLocal(captureDateSource),
  }))
  const captureDate =
    captureDateState.photoId === photo.id && captureDateState.source === captureDateSource
      ? captureDateState.value
      : toDateTimeLocal(captureDateSource)
  const [moderationPassword, setModerationPassword] = useState('')
  const swipeStartRef = useRef<{ x: number; y: number } | null>(null)
  const moderatedGroups = groups.filter(
    (group) => (photo.sharing.group_ids ?? []).includes(group.id) && group.current_user_role === 'admin',
  )
  const handleTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    if (event.touches.length !== 1) {
      swipeStartRef.current = null
      return
    }
    const touch = event.touches[0]
    swipeStartRef.current = { x: touch.clientX, y: touch.clientY }
  }
  const handleTouchEnd = (event: TouchEvent<HTMLDivElement>) => {
    const start = swipeStartRef.current
    swipeStartRef.current = null
    if (!start || updatingMetadata || event.changedTouches.length !== 1) return
    const touch = event.changedTouches[0]
    const deltaX = touch.clientX - start.x
    const deltaY = touch.clientY - start.y
    if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX || Math.abs(deltaX) <= Math.abs(deltaY)) return
    if (deltaX > 0) onPreviousPhoto?.()
    else onNextPhoto?.()
  }
  const saveMemo = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalized = memo.trim()
    onMemoSave(normalized || null)
  }
  const saveCaptureDate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onCaptureDateSave(captureDate ? `${captureDate}:00+09:00` : null)
  }

  return (
    <Dialog
      titleId="photo-title"
      overlayClassName="modal"
      className="modal__panel"
      closeClassName="modal__close"
      closeLabel={t('photoDetails.close')}
      size="large"
      surface="media"
      onClose={onClose}
    >
      <div
        className="modal__image-wrap"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={() => {
          swipeStartRef.current = null
        }}
      >
        <PhotoPreview photo={photo} className="modal__image" source="original" />
      </div>
      <div className="modal__details">
        <div>
          <p className="eyebrow">{t('photoDetails.eyebrow')}</p>
          <h2 id="photo-title">{photo.original_filename}</h2>
          <div className="photo-detail-actions">
            <button
              className={`secondary-button icon-button favorite-button ${photo.is_favorite ? 'favorite-button--active' : ''}`}
              type="button"
              disabled={updatingMetadata}
              aria-pressed={photo.is_favorite ?? false}
              onClick={onToggleFavorite}
            >
              {photo.is_favorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
              {t(photo.is_favorite ? 'photoDetails.removeFavorite' : 'photoDetails.addFavorite')}
            </button>
            <a className="secondary-button icon-button photo-download" href={getPhotoDownloadUrl(photo.id)} download>
              <SaveIcon />
              {t('photoDetails.downloadOriginal')}
            </a>
            {isOwner && (
              <button
                className="danger-button icon-button"
                type="button"
                disabled={updatingMetadata}
                onClick={() => {
                  void confirm(t('photoTrash.trashConfirm', { filename: photo.original_filename })).then(
                    (confirmed) => confirmed && onTrash(),
                  )
                }}
              >
                <DeleteIcon />
                {t('photoTrash.moveToTrash')}
              </button>
            )}
          </div>
        </div>
        <dl className="metadata-list">
          <div>
            <dt>{t('photoDetails.capturedAt')}</dt>
            <dd>
              {photo.captured_at ? formatDateTime(photo.captured_at) : t('common.unknown')}
              {photo.captured_at_override && <small> ({t('photoDetails.captureDateOverridden')})</small>}
            </dd>
          </div>
          <div>
            <dt>{t('photoDetails.uploadedAt')}</dt>
            <dd>{formatDateTime(photo.uploaded_at)}</dd>
          </div>
          <div>
            <dt>{t('photoDetails.uploadedBy')}</dt>
            <dd>{photo.uploaded_by_username}</dd>
          </div>
          <div>
            <dt>{t('photoDetails.fileType')}</dt>
            <dd>{formatPhotoContentType(photo.content_type)}</dd>
          </div>
          <div>
            <dt>{t('photoDetails.visibility')}</dt>
            <dd>
              {isOwner ? (
                <fieldset className="photo-sharing" disabled={updatingMetadata}>
                  <legend className="sr-only">{t('photoDetails.visibilityLabel')}</legend>
                  <small>
                    {(photo.sharing.group_ids ?? []).length === 0
                      ? t('photoUpload.private')
                      : t('photoUpload.sharedGroups')}
                  </small>
                  {groups.map((group) => {
                    const selected = (photo.sharing.group_ids ?? []).includes(group.id)
                    return (
                      <label key={group.id}>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() =>
                            onSharingChange(
                              selected
                                ? (photo.sharing.group_ids ?? []).filter((id) => id !== group.id)
                                : [...(photo.sharing.group_ids ?? []), group.id],
                            )
                          }
                        />
                        <span>{group.name}</span>
                      </label>
                    )
                  })}
                </fieldset>
              ) : (
                <div>
                  {moderatedGroups.length > 0 && onModerateGroupShare && (
                    <label>
                      {t('photoDetails.currentPassword')}
                      <input
                        type="password"
                        value={moderationPassword}
                        autoComplete="current-password"
                        disabled={updatingMetadata}
                        onChange={(event) => setModerationPassword(event.target.value)}
                      />
                    </label>
                  )}
                  {groups
                    .filter((group) => (photo.sharing.group_ids ?? []).includes(group.id))
                    .map((group) => (
                      <span key={group.id}>
                        {group.name}
                        {group.current_user_role === 'admin' && onModerateGroupShare && (
                          <button
                            className="danger-button"
                            type="button"
                            disabled={updatingMetadata || !moderationPassword}
                            onClick={() => {
                              onModerateGroupShare(group.id, moderationPassword)
                              setModerationPassword('')
                            }}
                          >
                            {t('photoDetails.removeFromGroup')}
                          </button>
                        )}
                      </span>
                    ))}
                </div>
              )}
            </dd>
          </div>
          <div>
            <dt>{t('photoDetails.imageSize')}</dt>
            <dd>{photo.width && photo.height ? `${photo.width} × ${photo.height}` : t('common.unknown')}</dd>
          </div>
          <div>
            <dt>{t('photoDetails.fileSize')}</dt>
            <dd>{formatBytes(photo.size_bytes)}</dd>
          </div>
        </dl>
        {isOwner && (
          <div className="photo-memo">
            <h3>{t('photoDetails.captureDateEdit')}</h3>
            <form onSubmit={saveCaptureDate}>
              <input
                type="datetime-local"
                value={captureDate}
                disabled={updatingMetadata}
                onChange={(event) =>
                  setCaptureDateState({ photoId: photo.id, source: captureDateSource, value: event.target.value })
                }
              />
              <div>
                <button
                  className="success-button icon-button"
                  type="submit"
                  disabled={updatingMetadata || !captureDate}
                >
                  <SaveIcon />
                  {updatingMetadata ? t('common.saving') : t('photoDetails.saveCaptureDate')}
                </button>
                {photo.captured_at_override && (
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={updatingMetadata}
                    onClick={() => onCaptureDateSave(null)}
                  >
                    {t('photoDetails.resetCaptureDate')}
                  </button>
                )}
              </div>
            </form>
          </div>
        )}
        <div className="photo-memo">
          <h3>{t('photoDetails.memo')}</h3>
          <form onSubmit={saveMemo}>
            <textarea
              value={memo}
              maxLength={2000}
              rows={5}
              disabled={updatingMetadata}
              placeholder={t('photoDetails.memoPlaceholder')}
              onChange={(event) => setMemo(event.target.value)}
            />
            <div>
              <small>{memo.length} / 2000</small>
              <button
                className="success-button icon-button"
                type="submit"
                disabled={updatingMetadata || memo.trim() === (photo.memo ?? '')}
              >
                <SaveIcon />
                {updatingMetadata ? t('common.saving') : t('photoDetails.saveMemo')}
              </button>
            </div>
            {photo.memo && (
              <small className="photo-memo__updated">
                {t('photoDetails.memoUpdatedBy', {
                  username: photo.memo_updated_by_username,
                  date: formatDateTime(photo.memo_updated_at),
                })}
              </small>
            )}
          </form>
        </div>
        {error && (
          <div className="page-message page-message--error" role="alert">
            {error}
          </div>
        )}
      </div>
    </Dialog>
  )
}

function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value))
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`
}
