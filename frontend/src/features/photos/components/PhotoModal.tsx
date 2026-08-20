import { useId, useRef, useState, type FormEvent, type TouchEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { formatBytes, formatDateTime } from '../../../shared/lib/format'
import { Dialog } from '../../../shared/ui/Dialog'
import { PageMessage } from '../../../shared/ui/PageMessage'
import { useConfirmation } from '../../../shared/ui/confirmation'
import { BackIcon, DeleteIcon, FavoriteBorderIcon, FavoriteIcon, RetryIcon, SaveIcon } from '../../../shared/ui/icons'
import type { FamilyGroup } from '../../groups/api'
import { getPhotoDownloadUrl, type Photo } from '../api'
import { formatPhotoContentType } from '../contentType'
import { PhotoPreview } from './PhotoPreview'

interface PhotoModalProps {
  photo: Photo
  photoDetailLoading?: boolean
  photoDetailError?: string | null
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
  onRetryPhotoDetail?: () => void
  onModerateGroupShare?: (groupId: string, currentPassword: string) => void
  onPreviousPhoto?: () => void
  onNextPhoto?: () => void
}

const SWIPE_THRESHOLD_PX = 50

export function PhotoModal({
  photo,
  photoDetailLoading = false,
  photoDetailError = null,
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
  onRetryPhotoDetail,
  onModerateGroupShare,
  onPreviousPhoto,
  onNextPhoto,
}: PhotoModalProps) {
  const { t } = useTranslation()
  const confirm = useConfirmation()
  const captureDateId = useId()
  const memoId = useId()
  const isOwner = photo.uploaded_by_user_id === currentUserId
  const metadataBusy = updatingMetadata || photoDetailLoading
  const [memoState, setMemoState] = useState(() => ({ photoId: photo.id, value: photo.memo ?? '' }))
  const memo = memoState.photoId === photo.id ? memoState.value : (photo.memo ?? '')
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
  const [displayDimensions, setDisplayDimensions] = useState<{
    photoId: string
    width: number
    height: number
  } | null>(null)
  const activeDimensions = displayDimensions?.photoId === photo.id ? displayDimensions : photo
  const mediaAspectRatio = `${activeDimensions.width} / ${activeDimensions.height}`
  const [moderationPasswordState, setModerationPasswordState] = useState(() => ({ photoId: photo.id, value: '' }))
  const moderationPassword = moderationPasswordState.photoId === photo.id ? moderationPasswordState.value : ''
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
    if (!start || metadataBusy || event.changedTouches.length !== 1) return
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
      size="extra-large"
      surface="media"
      onClose={onClose}
      overlayContent={
        <nav className="modal__edge-navigation" aria-label={t('photoDetails.navigationLabel')}>
          <button
            className="modal__edge-navigation-button modal__edge-navigation-button--previous"
            type="button"
            disabled={metadataBusy || !onPreviousPhoto}
            aria-label={t('photoDetails.previousPhoto')}
            onClick={onPreviousPhoto}
          >
            <BackIcon />
          </button>
          <button
            className="modal__edge-navigation-button modal__edge-navigation-button--next"
            type="button"
            disabled={metadataBusy || !onNextPhoto}
            aria-label={t('photoDetails.nextPhoto')}
            onClick={onNextPhoto}
          >
            <BackIcon />
          </button>
        </nav>
      }
    >
      {photoDetailError ? (
        <div className="modal__details photo-detail-error">
          <p className="eyebrow">{t('photoDetails.eyebrow')}</p>
          <h2 id="photo-title">{t('photos.detailFailed')}</h2>
          <PageMessage>{photoDetailError}</PageMessage>
          {onRetryPhotoDetail && (
            <button className="secondary-button icon-button" type="button" onClick={onRetryPhotoDetail}>
              <RetryIcon />
              {t('photos.retryDetail')}
            </button>
          )}
        </div>
      ) : (
        <>
          <div
            className="modal__image-wrap"
            style={{ aspectRatio: mediaAspectRatio }}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
            onTouchCancel={() => {
              swipeStartRef.current = null
            }}
          >
            <PhotoPreview
              key={photo.id}
              photo={photo}
              className="modal__image"
              source="original"
              onDisplayDimensions={(width, height) => {
                setDisplayDimensions((current) =>
                  current?.photoId === photo.id && current.width === width && current.height === height
                    ? current
                    : { photoId: photo.id, width, height },
                )
              }}
            />
          </div>
          <div className="modal__details">
            <div>
              <p className="eyebrow">{t('photoDetails.eyebrow')}</p>
              <h2 id="photo-title">{photo.original_filename}</h2>
              <div className="photo-detail-actions">
                <button
                  className={`secondary-button icon-button favorite-button ${photo.is_favorite ? 'favorite-button--active' : ''}`}
                  type="button"
                  disabled={metadataBusy}
                  aria-pressed={photo.is_favorite ?? false}
                  onClick={onToggleFavorite}
                >
                  {photo.is_favorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
                  {t(photo.is_favorite ? 'photoDetails.removeFavorite' : 'photoDetails.addFavorite')}
                </button>
                <a
                  className="secondary-button icon-button photo-download"
                  href={getPhotoDownloadUrl(photo.id)}
                  download
                >
                  <SaveIcon />
                  {t('photoDetails.downloadOriginal')}
                </a>
                {isOwner && (
                  <button
                    className="danger-button icon-button"
                    type="button"
                    disabled={metadataBusy}
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
                    <fieldset className="photo-sharing" disabled={metadataBusy}>
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
                        <label className="photo-sharing__password">
                          {t('photoDetails.currentPassword')}
                          <input
                            type="password"
                            value={moderationPassword}
                            autoComplete="current-password"
                            disabled={metadataBusy}
                            onChange={(event) =>
                              setModerationPasswordState({ photoId: photo.id, value: event.target.value })
                            }
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
                                disabled={metadataBusy || !moderationPassword}
                                onClick={() => {
                                  onModerateGroupShare(group.id, moderationPassword)
                                  setModerationPasswordState({ photoId: photo.id, value: '' })
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
                  <label className="sr-only" htmlFor={captureDateId}>
                    {t('photoDetails.captureDateEdit')}
                  </label>
                  <div className="photo-memo__datetime-field">
                    <input
                      id={captureDateId}
                      type="datetime-local"
                      value={captureDate}
                      disabled={metadataBusy}
                      onChange={(event) =>
                        setCaptureDateState({ photoId: photo.id, source: captureDateSource, value: event.target.value })
                      }
                    />
                  </div>
                  <div className="photo-memo__actions">
                    <button
                      className="success-button icon-button"
                      type="submit"
                      disabled={metadataBusy || !captureDate}
                    >
                      <SaveIcon />
                      {updatingMetadata ? t('common.saving') : t('photoDetails.saveCaptureDate')}
                    </button>
                    {photo.captured_at_override && (
                      <button
                        className="secondary-button"
                        type="button"
                        disabled={metadataBusy}
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
                <label className="sr-only" htmlFor={memoId}>
                  {t('photoDetails.memo')}
                </label>
                <textarea
                  id={memoId}
                  value={memo}
                  maxLength={2000}
                  rows={5}
                  disabled={metadataBusy}
                  placeholder={t('photoDetails.memoPlaceholder')}
                  onChange={(event) => setMemoState({ photoId: photo.id, value: event.target.value })}
                />
                <div className="photo-memo__actions">
                  <small>{memo.length} / 2000</small>
                  <button
                    className="success-button icon-button"
                    type="submit"
                    disabled={metadataBusy || memo.trim() === (photo.memo ?? '')}
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
            {error && <PageMessage>{error}</PageMessage>}
          </div>
        </>
      )}
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
