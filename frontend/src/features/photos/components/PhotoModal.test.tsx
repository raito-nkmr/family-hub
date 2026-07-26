import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Photo } from '../api'
import { PhotoModal } from './PhotoModal'

const photo: Photo = {
  id: 'photo-1',
  uploaded_by_user_id: 'owner-1',
  uploaded_by_username: 'owner',
  visibility: 'shared',
  sharing: { type: 'shared', group_ids: ['group-1'] },
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

describe('PhotoModal', () => {
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

    expect(panel).toHaveClass('dialog__panel--size-large', 'dialog__panel--surface-media')
    expect(favorite.parentElement).toHaveClass('photo-detail-actions')
    expect(favorite).toHaveClass('secondary-button', 'icon-button')
    expect(download).toHaveClass('secondary-button', 'icon-button')
    expect(trash).toHaveClass('danger-button', 'icon-button')
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
})
