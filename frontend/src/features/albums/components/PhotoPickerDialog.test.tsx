import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PhotoListItem } from '../../photos/api'
import { PhotoPickerDialog } from './PhotoPickerDialog'

const { usePhotoListMock } = vi.hoisted(() => ({ usePhotoListMock: vi.fn() }))

vi.mock('../../photos/usePhotoList', () => ({ usePhotoList: usePhotoListMock }))

const photoList = {
  photos: [] as PhotoListItem[],
  totalCount: 0,
  loading: false,
  loadingMore: false,
  hasMore: false,
  error: null,
  loadMoreFailed: false,
  loadMore: vi.fn(),
  refresh: vi.fn(),
}

describe('PhotoPickerDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    usePhotoListMock.mockReturnValue(photoList)
  })

  it('keeps album and group constraints while delegating search to the shared photo query', async () => {
    const user = userEvent.setup()
    render(
      <PhotoPickerDialog
        albumId="album-1"
        groupId="group-1"
        submitting={false}
        error={null}
        onUnauthorized={vi.fn()}
        onSubmit={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(usePhotoListMock).toHaveBeenLastCalledWith({
      filters: { excludeAlbumId: 'album-1', sharingGroupId: 'group-1' },
    })
    await user.click(screen.getByRole('button', { name: '検索条件を表示' }))
    await user.type(screen.getByRole('searchbox'), '旅行')
    await user.click(screen.getByRole('button', { name: '絞り込む' }))

    expect(usePhotoListMock).toHaveBeenLastCalledWith({
      filters: { q: '旅行', excludeAlbumId: 'album-1', sharingGroupId: 'group-1' },
    })
  })
})
