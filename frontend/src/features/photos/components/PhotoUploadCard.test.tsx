import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { StorageStatus } from '../api'
import type { QueuedUpload } from '../uploadTypes'
import { PhotoUploadCard } from './PhotoUploadCard'

const availableStorage: StorageStatus = {
  status: 'available',
  available: true,
  writable: true,
  free_bytes: 1024 ** 3,
  minimum_free_bytes: 1024,
  total_bytes: 2 * 1024 ** 3,
}

describe('PhotoUploadCard', () => {
  const queuedUpload = (name = 'photo.jpg'): QueuedUpload => ({
    clientId: name,
    file: new File(['photo'], name, { type: 'image/jpeg' }),
    status: 'queued',
    uploadedBytes: 0,
    errorCode: null,
    photoId: null,
  })

  it('toggles the compact mobile upload controls', async () => {
    const user = userEvent.setup()
    render(
      <PhotoUploadCard
        storage={availableStorage}
        uploadQueue={[]}
        uploading={false}
        groups={[]}
        selectedGroupIds={[]}
        visibilityLocked={false}
        uploadMessage={null}
        fileInputRef={createRef<HTMLInputElement>()}
        onFileChange={vi.fn()}
        onGroupSelectionChange={vi.fn()}
        onUpload={vi.fn()}
        onCancel={vi.fn()}
        onShareSavedPhotos={vi.fn()}
      />,
    )

    const openButton = screen.getByRole('button', { name: '開く' })
    expect(openButton).toHaveAttribute('aria-expanded', 'false')

    await user.click(openButton)
    expect(screen.getByRole('button', { name: '閉じる' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('shows multiple selected files and enables upload when storage is available', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn()
    render(
      <PhotoUploadCard
        storage={availableStorage}
        uploadQueue={[queuedUpload(), queuedUpload('second.jpg')]}
        uploading={false}
        groups={[]}
        selectedGroupIds={[]}
        visibilityLocked={false}
        uploadMessage={null}
        fileInputRef={createRef<HTMLInputElement>()}
        onFileChange={vi.fn()}
        onGroupSelectionChange={vi.fn()}
        onUpload={onUpload}
        onCancel={vi.fn()}
        onShareSavedPhotos={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'ストレージへ保存' }))

    expect(onUpload).toHaveBeenCalledOnce()
    expect(screen.getByText('photo.jpg')).toBeInTheDocument()
    expect(screen.getByText('second.jpg')).toBeInTheDocument()
    expect(screen.getByText('2枚の写真')).toBeInTheDocument()
  })

  it('disables upload while storage is unavailable', () => {
    const unavailableStorage = { ...availableStorage, status: 'read_only' as const, available: false, writable: false }
    render(
      <PhotoUploadCard
        storage={unavailableStorage}
        uploadQueue={[queuedUpload()]}
        uploading={false}
        groups={[]}
        selectedGroupIds={[]}
        visibilityLocked={false}
        uploadMessage={null}
        fileInputRef={createRef<HTMLInputElement>()}
        onFileChange={vi.fn()}
        onGroupSelectionChange={vi.fn()}
        onUpload={vi.fn()}
        onCancel={vi.fn()}
        onShareSavedPhotos={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'ストレージへ保存' })).toBeDisabled()
    expect(screen.getByText('HDDが読み取り専用です')).toBeInTheDocument()
  })

  it('offers to share photos saved by the current upload', async () => {
    const user = userEvent.setup()
    const onShareSavedPhotos = vi.fn()
    render(
      <PhotoUploadCard
        storage={availableStorage}
        uploadQueue={[{ ...queuedUpload(), status: 'succeeded', uploadedBytes: 5, photoId: 'photo-1' }]}
        uploading={false}
        groups={[]}
        selectedGroupIds={[]}
        visibilityLocked={false}
        uploadMessage={null}
        fileInputRef={createRef<HTMLInputElement>()}
        onFileChange={vi.fn()}
        onGroupSelectionChange={vi.fn()}
        onUpload={vi.fn()}
        onCancel={vi.fn()}
        onShareSavedPhotos={onShareSavedPhotos}
      />,
    )

    const shareButton = screen.getByRole('button', { name: '保存した1枚をまとめて共有' })
    expect(shareButton.querySelector('svg')).toBeInTheDocument()

    await user.click(shareButton)
    expect(onShareSavedPhotos).toHaveBeenCalledWith(['photo-1'])
  })
})
