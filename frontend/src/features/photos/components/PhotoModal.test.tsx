import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Photo, PhotoListItem } from '../api'
import { PhotoModal } from './PhotoModal'

const photo: Photo = {
  id: 'photo-1',
  uploaded_by_user_id: 'owner-1',
  uploaded_by_username: 'owner',
  visibility: 'shared',
  sharing: { group_ids: ['group-1'] },
  is_favorite: false,
  memo: '旅行のメモ',
  memo_updated_by_user_id: 'viewer-1',
  memo_updated_by_username: 'viewer',
  memo_updated_at: '2026-07-15T01:00:00Z',
  metadata_version: 2,
  original_filename: 'photo.jpg',
  storage_key: 'originals/2026/07/photo-1.jpg',
  content_type: 'image/jpeg',
  size_bytes: 5,
  sha256: 'a'.repeat(64),
  width: 100,
  height: 100,
  captured_at: null,
  uploaded_at: '2026-07-15T00:00:00Z',
  lifecycle_state: 'active',
  trashed_at: null,
  purge_after: null,
  purge_requested_at: null,
}

const photoSummary: PhotoListItem = {
  id: photo.id,
  uploaded_by_user_id: photo.uploaded_by_user_id,
  uploaded_by_username: photo.uploaded_by_username,
  visibility: photo.visibility,
  is_favorite: photo.is_favorite,
  original_filename: photo.original_filename,
  content_type: photo.content_type,
  width: photo.width,
  height: photo.height,
  captured_at: photo.captured_at,
  uploaded_at: photo.uploaded_at,
}

describe('PhotoModal', () => {
  it.each([
    { label: 'portrait', width: 3024, height: 4032, aspectRatio: '3024 / 4032' },
    { label: 'landscape', width: 4032, height: 2268, aspectRatio: '4032 / 2268' },
    { label: 'square', width: 1200, height: 1200, aspectRatio: '1200 / 1200' },
  ])('uses the original dimensions for a $label media stage', ({ width, height, aspectRatio }) => {
    const { container } = render(
      <PhotoModal
        photo={{ ...photo, width, height }}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
      />,
    )

    expect(container.querySelector('.modal__image-wrap')).toHaveStyle({ aspectRatio })
  })

  it('updates the media stage to the decoded display orientation', () => {
    const { container } = render(
      <PhotoModal
        photo={{ ...photo, width: 4032, height: 3024 }}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
      />,
    )
    const image = screen.getByAltText('photo.jpg')
    Object.defineProperties(image, {
      naturalWidth: { value: 3024 },
      naturalHeight: { value: 4032 },
    })

    fireEvent.load(image)

    expect(container.querySelector('.modal__image-wrap')).toHaveStyle({ aspectRatio: '3024 / 4032' })
  })

  it('moves to adjacent photos when desktop edge controls are clicked', () => {
    const onPreviousPhoto = vi.fn()
    const onNextPhoto = vi.fn()
    render(
      <PhotoModal
        photo={photo}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
        onPreviousPhoto={onPreviousPhoto}
        onNextPhoto={onNextPhoto}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '前の写真を表示' }))
    fireEvent.click(screen.getByRole('button', { name: '次の写真を表示' }))

    expect(onPreviousPhoto).toHaveBeenCalledOnce()
    expect(onNextPhoto).toHaveBeenCalledOnce()
  })

  it('hides the previous photo when detail loading fails and offers retry', () => {
    const onRetryPhotoDetail = vi.fn()
    render(
      <PhotoModal
        photo={photo}
        photoDetailError="Could not load photo details."
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
        onRetryPhotoDetail={onRetryPhotoDetail}
      />,
    )

    expect(screen.queryByText('photo.jpg')).not.toBeInTheDocument()
    expect(screen.getByText('Could not load photo details.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '詳細の読み込みを再試行' }))

    expect(onRetryPhotoDetail).toHaveBeenCalledOnce()
  })

  it('shows the list summary while the detail request is loading', () => {
    render(
      <PhotoModal
        photo={photoSummary}
        photoDetailLoading
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading', { name: 'photo.jpg' })).toBeInTheDocument()
    expect(screen.getByText('読み込み中…')).toBeInTheDocument()
    expect(screen.queryByLabelText('共有メモ')).not.toBeInTheDocument()
  })

  it('shows the list summary and retry action when detail loading fails initially', () => {
    const onRetryPhotoDetail = vi.fn()
    render(
      <PhotoModal
        photo={photoSummary}
        photoDetailError="Could not load photo details."
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
        onRetryPhotoDetail={onRetryPhotoDetail}
      />,
    )

    expect(screen.getByRole('heading', { name: 'photo.jpg' })).toBeInTheDocument()
    expect(screen.getByText('Could not load photo details.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '詳細の読み込みを再試行' }))

    expect(onRetryPhotoDetail).toHaveBeenCalledOnce()
  })

  it('moves to adjacent photos for horizontal touch gestures', () => {
    const onPreviousPhoto = vi.fn()
    const onNextPhoto = vi.fn()
    const { container } = render(
      <PhotoModal
        photo={photo}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
        onPreviousPhoto={onPreviousPhoto}
        onNextPhoto={onNextPhoto}
      />,
    )

    const imageWrap = container.querySelector('.modal__image-wrap')!
    fireEvent.touchStart(imageWrap, { touches: [{ clientX: 100, clientY: 100 }] })
    fireEvent.touchEnd(imageWrap, { changedTouches: [{ clientX: 180, clientY: 105 }] })
    fireEvent.touchStart(imageWrap, { touches: [{ clientX: 180, clientY: 100 }] })
    fireEvent.touchEnd(imageWrap, { changedTouches: [{ clientX: 100, clientY: 105 }] })

    expect(onPreviousPhoto).toHaveBeenCalledOnce()
    expect(onNextPhoto).toHaveBeenCalledOnce()
  })

  it('ignores short and mostly vertical touch gestures', () => {
    const onPreviousPhoto = vi.fn()
    const onNextPhoto = vi.fn()
    const { container } = render(
      <PhotoModal
        photo={photo}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
        onPreviousPhoto={onPreviousPhoto}
        onNextPhoto={onNextPhoto}
      />,
    )

    const imageWrap = container.querySelector('.modal__image-wrap')!
    fireEvent.touchStart(imageWrap, { touches: [{ clientX: 100, clientY: 100 }] })
    fireEvent.touchEnd(imageWrap, { changedTouches: [{ clientX: 140, clientY: 101 }] })
    fireEvent.touchStart(imageWrap, { touches: [{ clientX: 100, clientY: 100 }] })
    fireEvent.touchEnd(imageWrap, { changedTouches: [{ clientX: 180, clientY: 250 }] })

    expect(onPreviousPhoto).not.toHaveBeenCalled()
    expect(onNextPhoto).not.toHaveBeenCalled()
  })

  it('groups owner actions with consistent button styling', () => {
    render(
      <PhotoModal
        photo={photo}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
      />,
    )

    const favorite = screen.getByRole('button', { name: /お気に入りに追加/ })
    const download = screen.getByRole('link', { name: 'ダウンロード' })
    const trash = screen.getByRole('button', { name: 'ゴミ箱へ移動' })
    const panel = screen.getByRole('dialog').firstElementChild

    expect(panel).toHaveClass('dialog__panel--size-extra-large', 'dialog__panel--surface-media')
    expect(favorite.parentElement).toHaveClass('photo-detail-actions')
    expect(favorite).toHaveClass('secondary-button', 'icon-button')
    expect(download).toHaveClass('secondary-button', 'icon-button')
    expect(trash).toHaveClass('danger-button', 'icon-button')
    expect(screen.getByText('JPEG')).toBeInTheDocument()
  })

  it('lets a viewer edit the shared memo without exposing sharing controls', () => {
    const onMemoSave = vi.fn()
    const onToggleFavorite = vi.fn()

    render(
      <PhotoModal
        photo={photo}
        currentUserId="viewer-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={onToggleFavorite}
        onMemoSave={onMemoSave}
        onTrash={vi.fn()}
      />,
    )

    expect(screen.queryByLabelText('写真の公開範囲')).not.toBeInTheDocument()
    const memo = screen.getByPlaceholderText('この写真を見られる人に共有するメモ')
    fireEvent.change(memo, { target: { value: 'みんなで見るメモ' } })
    fireEvent.click(screen.getByRole('button', { name: '共有メモを保存' }))

    expect(onMemoSave).toHaveBeenCalledWith('みんなで見るメモ')
    expect(screen.getByText(/viewer/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /お気に入りに追加/ }))
    expect(onToggleFavorite).toHaveBeenCalledOnce()
  })

  it('associates metadata editors with accessible labels', () => {
    render(
      <PhotoModal
        photo={photo}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onTrash={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('撮影日時を補正')).toHaveAttribute('type', 'datetime-local')
    expect(screen.getByLabelText('共有メモ')).toHaveValue('旅行のメモ')
  })

  it('syncs the capture date input after resetting an override', () => {
    const onCaptureDateSave = vi.fn()
    const overriddenPhoto = {
      ...photo,
      captured_at: '2026-07-14T00:00:00Z',
      captured_at_override: '2026-07-15T03:04:00Z',
    }
    const { rerender } = render(
      <PhotoModal
        photo={overriddenPhoto}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onCaptureDateSave={onCaptureDateSave}
        onTrash={vi.fn()}
      />,
    )

    const input = screen.getByDisplayValue('2026-07-15T12:04')
    fireEvent.click(screen.getByRole('button', { name: '元のEXIF値に戻す' }))

    expect(onCaptureDateSave).toHaveBeenCalledWith(null)

    rerender(
      <PhotoModal
        photo={{ ...overriddenPhoto, captured_at_override: null }}
        currentUserId="owner-1"
        updatingMetadata={false}
        error={null}
        groups={[]}
        onClose={vi.fn()}
        onSharingChange={vi.fn()}
        onToggleFavorite={vi.fn()}
        onMemoSave={vi.fn()}
        onCaptureDateSave={onCaptureDateSave}
        onTrash={vi.fn()}
      />,
    )

    expect(screen.getByDisplayValue('2026-07-14T09:00')).toBe(input)
  })
})
