import { useId, useState, type RefObject } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { formatBytes } from '../../../shared/lib/format'
import { AddPhotoIcon, CancelIcon, RetryIcon, SaveIcon, ShareIcon, UploadIcon } from '../../../shared/ui/icons'
import type { FamilyGroup } from '../../groups/api'
import type { StorageStatus } from '../api'
import type { LocalUploadStatus, QueuedUpload } from '../uploadTypes'

export interface UploadMessage {
  type: 'success' | 'error'
  text: string
}

interface PhotoUploadCardProps {
  storage: StorageStatus | null
  uploadQueue: QueuedUpload[]
  uploading: boolean
  groups: FamilyGroup[]
  selectedGroupIds: string[]
  visibilityLocked: boolean
  uploadMessage: UploadMessage | null
  fileInputRef: RefObject<HTMLInputElement | null>
  onFileChange: (files: File[]) => void
  onGroupSelectionChange: (groupIds: string[]) => void
  onUpload: () => void
  onCancel: () => void
  onShareSavedPhotos: (photoIds: string[]) => void
}

function getUploadStatusLabel(item: QueuedUpload, t: TFunction): string {
  if (item.errorCode === 'invalid_photo') return t('photoUpload.status.invalid')
  if (item.errorCode === 'canceled') return t('photoUpload.status.canceled')
  return t(`photoUpload.status.${item.status as LocalUploadStatus}`)
}

export function PhotoUploadCard({
  storage,
  uploadQueue,
  uploading,
  groups,
  selectedGroupIds,
  visibilityLocked,
  uploadMessage,
  fileInputRef,
  onFileChange,
  onGroupSelectionChange,
  onUpload,
  onCancel,
  onShareSavedPhotos,
}: PhotoUploadCardProps) {
  const { t } = useTranslation()
  const fileInputId = useId()
  const bodyId = useId()
  const [expanded, setExpanded] = useState(false)
  const totalBytes = uploadQueue.reduce((total, item) => total + item.file.size, 0)
  const hasUploadableItem = uploadQueue.some(
    (item) => !['succeeded', 'duplicate'].includes(item.status) && item.errorCode !== 'invalid_photo',
  )
  const savedPhotoIds = uploadQueue.flatMap((item) =>
    item.status === 'succeeded' && item.photoId ? [item.photoId] : [],
  )
  const isExpanded = expanded || uploading

  return (
    <aside className={`upload-card${isExpanded ? ' upload-card--expanded' : ''}`} aria-labelledby="upload-heading">
      <div className="upload-card__heading">
        <div>
          <h2 id="upload-heading">{t('photoUpload.title')}</h2>
        </div>
        <UploadIcon />
        <button
          className="upload-card__toggle"
          type="button"
          aria-expanded={isExpanded}
          aria-controls={bodyId}
          disabled={uploading}
          onClick={() => setExpanded((current) => !current)}
        >
          {t(isExpanded ? 'photoUpload.collapse' : 'photoUpload.expand')}
          <span aria-hidden="true">{isExpanded ? '−' : '+'}</span>
        </button>
      </div>

      <div className="upload-card__body" id={bodyId}>
        <label className={`file-picker ${uploadQueue.length > 0 ? 'file-picker--selected' : ''}`} htmlFor={fileInputId}>
          <input
            ref={fileInputRef}
            id={fileInputId}
            type="file"
            multiple
            disabled={uploading}
            accept="image/jpeg,image/jpg,image/png,image/heic,image/heif,.jpg,.jpeg,.png,.heic,.heif"
            onChange={(event) => {
              const files = Array.from(event.target.files ?? [])
              event.currentTarget.value = ''
              onFileChange(files)
            }}
          />
          <span className="file-picker__icon">
            <AddPhotoIcon />
          </span>
          {uploadQueue.length > 0 ? (
            <span className="file-picker__text">
              <strong>{t('photoUpload.selected', { count: uploadQueue.length })}</strong>
              <small>{t('photoUpload.totalSize', { size: formatBytes(totalBytes) })}</small>
            </span>
          ) : (
            <span className="file-picker__text">
              <strong>{t('photoUpload.chooseTitle')}</strong>
              <small>{t('photoUpload.formats')}</small>
            </span>
          )}
          <span className="file-picker__action">{t('photoUpload.choose')}</span>
        </label>

        <fieldset className="upload-visibility" disabled={uploading || visibilityLocked}>
          <legend>{t('photoUpload.visibility')}</legend>
          <small>{selectedGroupIds.length === 0 ? t('photoUpload.private') : t('photoUpload.sharedGroups')}</small>
          {groups.map((group) => (
            <label key={group.id}>
              <input
                type="checkbox"
                checked={selectedGroupIds.includes(group.id)}
                onChange={() =>
                  onGroupSelectionChange(
                    selectedGroupIds.includes(group.id)
                      ? selectedGroupIds.filter((id) => id !== group.id)
                      : [...selectedGroupIds, group.id],
                  )
                }
              />
              <span>{group.name}</span>
            </label>
          ))}
        </fieldset>

        {uploadQueue.length > 0 && (
          <ul className="upload-queue" aria-label={t('photoUpload.queueLabel')}>
            {uploadQueue.map((item) => {
              const progress = item.file.size === 0 ? 0 : Math.round((item.uploadedBytes / item.file.size) * 100)
              return (
                <li className="upload-queue__item" key={item.clientId}>
                  <div className="upload-queue__summary">
                    <span title={item.file.name}>{item.file.name}</span>
                    <small>{getUploadStatusLabel(item, t)}</small>
                  </div>
                  <progress max={100} value={progress} aria-label={`${item.file.name} ${progress}%`} />
                </li>
              )
            })}
          </ul>
        )}

        <div className="upload-actions">
          <button
            className="upload-button"
            type="button"
            onClick={onUpload}
            disabled={!hasUploadableItem || uploading || !storage?.available}
          >
            {uploading ? (
              <>
                <span className="spinner" />
                {t('photoUpload.uploading')}
              </>
            ) : uploadQueue.some((item) => item.status === 'failed') ? (
              <>
                <RetryIcon />
                {t('photoUpload.retry')}
              </>
            ) : (
              <>
                <SaveIcon />
                {t('photoUpload.save')}
              </>
            )}
          </button>
          {uploading && (
            <button className="upload-cancel-button upload-cancel-button--danger" type="button" onClick={onCancel}>
              <CancelIcon />
              {t('photoUpload.cancel')}
            </button>
          )}
          {!uploading && savedPhotoIds.length > 0 && (
            <button className="upload-cancel-button" type="button" onClick={() => onShareSavedPhotos(savedPhotoIds)}>
              <ShareIcon />
              {t('photoUpload.shareSaved', { count: savedPhotoIds.length })}
            </button>
          )}
        </div>

        {uploadMessage && (
          <p className={`form-message form-message--${uploadMessage.type}`} role="status">
            {uploadMessage.text}
          </p>
        )}
        {storage && !storage.available && (
          <p className="form-message form-message--error">{t(`storage.${storage.status}`)}</p>
        )}
        {storage?.free_bytes != null && (
          <p className="storage-capacity">{t('photoUpload.freeSpace', { size: formatBytes(storage.free_bytes) })}</p>
        )}
      </div>
    </aside>
  )
}
