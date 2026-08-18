import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getTrashedPhotos, restorePhoto, type Photo } from './api'
import { PhotoTrashPage } from './PhotoTrashPage'
import { createAppWrapper } from '../../test/renderWithAppProviders'

vi.mock('./api', () => ({
  getTrashedPhotos: vi.fn(),
  getTrashedPhotoThumbnailUrl: (photoId: string) => `/trash/${photoId}/thumbnail`,
  permanentlyDeletePhoto: vi.fn(),
  restorePhoto: vi.fn(),
}))

const photo: Photo = {
  id: 'photo-1',
  uploaded_by_user_id: 'user-1',
  uploaded_by_username: 'owner',
  visibility: 'private',
  sharing: { type: 'private', group_ids: [] },
  is_favorite: false,
  memo: null,
  memo_updated_by_user_id: 'user-1',
  memo_updated_by_username: 'owner',
  memo_updated_at: '2026-07-15T00:00:00Z',
  metadata_version: 1,
  original_filename: 'trashed.jpg',
  storage_key: 'originals/2026/07/photo-1.jpg',
  content_type: 'image/jpeg',
  size_bytes: 5,
  sha256: 'a'.repeat(64),
  width: 100,
  height: 100,
  captured_at: null,
  uploaded_at: '2026-07-15T00:00:00Z',
  lifecycle_state: 'trashed',
  trashed_at: '2026-07-18T00:00:00Z',
  purge_after: '2026-08-17T00:00:00Z',
  purge_requested_at: null,
}

describe('PhotoTrashPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem('family-hub-photo-grid-columns')
    vi.mocked(getTrashedPhotos).mockResolvedValue({ items: [photo], next_cursor: null, total_count: 1 })
    vi.mocked(restorePhoto).mockResolvedValue({ ...photo, lifecycle_state: 'active' })
  })

  it('uses the library grid density and opens actions in a dialog', async () => {
    const user = userEvent.setup()
    const { container } = render(<PhotoTrashPage onUnauthorized={vi.fn()} onLibraryChanged={vi.fn()} />, {
      wrapper: createAppWrapper(),
    })

    await screen.findByRole('button', { name: 'ゴミ箱のtrashed.jpgを開く' })
    expect(container.querySelector('.photo-grid')).toHaveClass('photo-grid--columns-3')

    await user.click(screen.getByRole('button', { name: '4列で表示' }))
    expect(container.querySelector('.photo-grid')).toHaveClass('photo-grid--columns-4')
    expect(localStorage.getItem('family-hub-photo-grid-columns')).toBe('4')

    await user.click(screen.getByRole('button', { name: 'ゴミ箱のtrashed.jpgを開く' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'trashed.jpg' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '復元する' })).toBeInTheDocument()
  })

  it('uses the shared decorated icon treatment for an empty trash', async () => {
    vi.mocked(getTrashedPhotos).mockResolvedValue({ items: [], next_cursor: null, total_count: 0 })
    const { container } = render(<PhotoTrashPage onUnauthorized={vi.fn()} onLibraryChanged={vi.fn()} />, {
      wrapper: createAppWrapper(),
    })

    await screen.findByRole('heading', { name: 'ゴミ箱は空です' })
    expect(container.querySelector('.empty-state > span > svg')).toBeInTheDocument()
  })

  it('restores the selected photo and removes it from the grid', async () => {
    const user = userEvent.setup()
    const onLibraryChanged = vi.fn()
    render(<PhotoTrashPage onUnauthorized={vi.fn()} onLibraryChanged={onLibraryChanged} />, {
      wrapper: createAppWrapper(),
    })

    await user.click(await screen.findByRole('button', { name: 'ゴミ箱のtrashed.jpgを開く' }))
    await user.click(screen.getByRole('button', { name: '復元する' }))

    await waitFor(() => expect(restorePhoto).toHaveBeenCalledWith('photo-1', expect.anything()))
    expect(screen.queryByRole('button', { name: 'ゴミ箱のtrashed.jpgを開く' })).not.toBeInTheDocument()
    expect(onLibraryChanged).toHaveBeenCalledOnce()
  })

  it('allows retrying restore after the first request fails', async () => {
    const user = userEvent.setup()
    vi.mocked(restorePhoto).mockRejectedValueOnce(new Error('restore failed'))
    render(<PhotoTrashPage onUnauthorized={vi.fn()} onLibraryChanged={vi.fn()} />, { wrapper: createAppWrapper() })

    await user.click(await screen.findByRole('button', { name: 'ゴミ箱のtrashed.jpgを開く' }))
    await user.click(screen.getByRole('button', { name: '復元する' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('写真を復元できませんでした。')
    expect(screen.getByRole('button', { name: '復元する' })).not.toBeDisabled()
  })

  it('announces an asynchronous load error', async () => {
    vi.mocked(getTrashedPhotos).mockRejectedValue(new Error('network unavailable'))

    render(<PhotoTrashPage onUnauthorized={vi.fn()} onLibraryChanged={vi.fn()} />, { wrapper: createAppWrapper() })

    expect(await screen.findByRole('alert')).toHaveTextContent('ゴミ箱を読み込めませんでした。')
  })

  it('loads the next trash page from the cursor', async () => {
    const secondPhoto = { ...photo, id: 'photo-2', original_filename: 'second.jpg' }
    vi.mocked(getTrashedPhotos)
      .mockResolvedValueOnce({ items: [photo], next_cursor: 'next-page', total_count: 2 })
      .mockResolvedValueOnce({ items: [secondPhoto], next_cursor: null, total_count: 2 })
    const user = userEvent.setup()
    render(<PhotoTrashPage onUnauthorized={vi.fn()} onLibraryChanged={vi.fn()} />, {
      wrapper: createAppWrapper(),
    })

    await user.click(await screen.findByRole('button', { name: '次の写真を読み込む' }))

    expect(await screen.findByRole('button', { name: 'ゴミ箱のsecond.jpgを開く' })).toBeInTheDocument()
    expect(getTrashedPhotos).toHaveBeenLastCalledWith(expect.any(AbortSignal), 'next-page')
  })
})
