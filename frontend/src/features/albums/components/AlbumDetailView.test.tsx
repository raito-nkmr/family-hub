import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Photo } from '../../photos/public'
import type { AlbumDetail } from '../api'
import { AlbumDetailView } from './AlbumDetailView'

const firstPhoto: Photo = {
  id: 'photo-1',
  uploaded_by_user_id: 'owner-1',
  uploaded_by_username: 'owner',
  visibility: 'shared',
  sharing: { group_ids: ['group-1'] },
  is_favorite: false,
  memo: 'Trip memo',
  memo_updated_by_user_id: 'owner-1',
  memo_updated_by_username: 'owner',
  memo_updated_at: '2026-07-15T01:00:00Z',
  metadata_version: 2,
  original_filename: 'first.jpg',
  storage_key: 'originals/2026/07/photo-1.jpg',
  content_type: 'image/jpeg',
  size_bytes: 5,
  sha256: 'a'.repeat(64),
  width: 100,
  height: 100,
  captured_at_original: null,
  captured_at_override: null,
  uploaded_at: '2026-07-15T00:00:00Z',
  effective_captured_at: '2026-07-15T00:00:00Z',
  lifecycle_state: 'active',
  trashed_at: null,
  purge_after: null,
  purge_requested_at: null,
}

const secondPhoto: Photo = {
  ...firstPhoto,
  id: 'photo-2',
  original_filename: 'second.jpg',
  storage_key: 'originals/2026/07/photo-2.jpg',
  sha256: 'b'.repeat(64),
}

const album: AlbumDetail = {
  id: 'album-1',
  title: '北海道旅行',
  description: null,
  created_by_user_id: 'owner-1',
  created_by_username: 'owner',
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T00:00:00Z',
  photo_count: 2,
  group_ids: ['group-1'],
  group_names: ['同居家族'],
  cover_photo_id: firstPhoto.id,
  photos: [firstPhoto, secondPhoto],
  next_cursor: null,
}

function renderView(overrides: Partial<React.ComponentProps<typeof AlbumDetailView>> = {}) {
  const props: React.ComponentProps<typeof AlbumDetailView> = {
    album,
    error: null,
    removingPhotoIds: new Set(),
    hasMore: false,
    loadingMore: false,
    loadMoreFailed: false,
    onBack: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onAddPhotos: vi.fn(),
    onSelectPhoto: vi.fn(),
    onRemovePhotos: vi.fn().mockResolvedValue(true),
    onSetCover: vi.fn().mockResolvedValue(true),
    onLoadMore: vi.fn(),
    ...overrides,
  }
  render(<AlbumDetailView {...props} />)
  return props
}

describe('AlbumDetailView', () => {
  it('keeps management actions out of browse mode', () => {
    const props = renderView()

    expect(screen.queryByRole('button', { name: '表紙にする' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'アルバムから外す' })).not.toBeInTheDocument()
    expect(screen.getByText('表紙')).toBeInTheDocument()
    const coverFrame = document.querySelector('.album-detail-header__cover')
    const firstPhotoFrame = document.querySelector(`.album-photo-card__image-wrap[data-photo-id="${firstPhoto.id}"]`)
    const coverImage = coverFrame?.querySelector('img')
    const firstPhotoImage = firstPhotoFrame?.querySelector('img')
    expect(coverFrame).toHaveAttribute('data-photo-id', firstPhoto.id)
    expect(firstPhotoFrame).toHaveAttribute('data-photo-id', firstPhoto.id)
    expect(coverImage).toHaveAttribute('src', '/api/v1/photos/photo-1/thumbnail')
    expect(coverImage).toHaveAttribute('src', firstPhotoImage?.getAttribute('src'))

    fireEvent.click(screen.getByRole('button', { name: /second.jpg/ }))
    expect(props.onSelectPhoto).toHaveBeenCalledWith(secondPhoto)
  })

  it('selects photos and exposes contextual actions in organize mode', async () => {
    const props = renderView()

    const organizeButton = screen.getByRole('button', { name: '写真を整理' })
    expect(organizeButton.querySelectorAll('.album-organize-toggle__content')).toHaveLength(2)
    fireEvent.click(organizeButton)

    expect(screen.getByRole('button', { name: '完了' })).toHaveClass('success-button')
    fireEvent.click(screen.getByRole('button', { name: /second.jpg/ }))

    expect(screen.getByText('1枚選択')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '表紙にする' }))
    await waitFor(() => expect(props.onSetCover).toHaveBeenCalledWith(secondPhoto))

    fireEvent.click(screen.getByRole('button', { name: /first.jpg/ }))
    fireEvent.click(screen.getByRole('button', { name: /second.jpg/ }))
    fireEvent.click(screen.getByRole('button', { name: 'アルバムから外す' }))

    await waitFor(() => expect(props.onRemovePhotos).toHaveBeenCalledWith(['photo-1', 'photo-2']))
    expect(props.onSelectPhoto).toHaveBeenCalledTimes(0)
  })
})
