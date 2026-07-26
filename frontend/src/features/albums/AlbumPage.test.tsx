import { render, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { getAlbums } from './api'
import { AlbumPage } from './AlbumPage'

vi.mock('./api', () => ({
  addPhotosToAlbum: vi.fn(),
  createAlbum: vi.fn(),
  deleteAlbum: vi.fn(),
  getAlbum: vi.fn(),
  getAlbums: vi.fn(),
  removePhotoFromAlbum: vi.fn(),
  updateAlbum: vi.fn(),
}))
vi.mock('../groups/api', () => ({ getGroups: vi.fn().mockResolvedValue([]) }))

describe('AlbumPage', () => {
  it('returns control to the app when the session expires', async () => {
    vi.mocked(getAlbums).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()

    render(<AlbumPage onUnauthorized={onUnauthorized} onSelectPhoto={vi.fn()} />, { wrapper: createAppWrapper() })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })
})
