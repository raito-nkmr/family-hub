import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { PhotoListItem, PhotoTimeline } from '../api'
import { PhotoLibrary } from './PhotoLibrary'

const photo: PhotoListItem = {
  id: 'photo-1',
  uploaded_by_user_id: 'user-1',
  uploaded_by_username: 'owner',
  visibility: 'private',
  original_filename: 'summer.jpg',
  content_type: 'image/jpeg',
  width: 100,
  height: 100,
  captured_at_original: '2025-07-15T00:00:00Z',
  captured_at_override: null,
  uploaded_at: '2025-07-15T00:00:00Z',
  effective_captured_at: '2025-07-15T00:00:00Z',
  is_favorite: false,
}

const timeline: PhotoTimeline = {
  year: 2025,
  months: [{ month: '2025-07', count: 1 }],
}

const callbacks = {
  currentUserId: 'user-1',
  onRefresh: vi.fn(),
  onSearch: vi.fn(),
  onTimelineYearChange: vi.fn(),
  onLoadMore: vi.fn(),
  onSelectPhoto: vi.fn(),
  onRequestBulkSharing: vi.fn(),
  onRequestExport: vi.fn(),
}

describe('PhotoLibrary', () => {
  beforeEach(() => {
    localStorage.removeItem('family-hub-photo-grid-columns')
  })

  it('shows skeletons during the initial load', () => {
    render(
      <PhotoLibrary
        photos={[]}
        filters={{}}
        timeline={null}
        totalCount={0}
        loading
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
      />,
    )

    expect(screen.getByLabelText('写真を読み込み中')).toBeInTheDocument()
  })

  it('keeps existing photos mounted while applying a filter', () => {
    const { container } = render(
      <PhotoLibrary
        photos={[photo]}
        filters={{}}
        timeline={timeline}
        totalCount={1}
        loading
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
      />,
    )

    expect(screen.getByAltText('summer.jpg')).toBeInTheDocument()
    expect(screen.queryByText('summer.jpg')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '2025年7月' })).toBeInTheDocument()
    expect(container.querySelector('.photo-badge--shared')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('写真を読み込み中')).not.toBeInTheDocument()
  })

  it('defaults to three columns and persists the mobile grid selection', async () => {
    const user = userEvent.setup()
    const { container } = render(
      <PhotoLibrary
        photos={[photo]}
        filters={{}}
        timeline={timeline}
        totalCount={1}
        loading={false}
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
      />,
    )

    expect(container.querySelector('.photo-grid')).toHaveClass('photo-grid--columns-3')
    expect(screen.getByRole('button', { name: '3列で表示' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: '4列で表示' }))

    expect(container.querySelector('.photo-grid')).toHaveClass('photo-grid--columns-4')
    expect(localStorage.getItem('family-hub-photo-grid-columns')).toBe('4')
  })

  it('selects all visible photos while keeping bulk sharing owner-only', async () => {
    const user = userEvent.setup()
    const onRequestBulkSharing = vi.fn()
    const onRequestExport = vi.fn()
    const sharedByAnotherUser = {
      ...photo,
      id: 'photo-2',
      uploaded_by_user_id: 'user-2',
      original_filename: 'shared.jpg',
    }
    render(
      <PhotoLibrary
        photos={[photo, sharedByAnotherUser]}
        filters={{}}
        timeline={timeline}
        totalCount={2}
        loading={false}
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
        onRequestBulkSharing={onRequestBulkSharing}
        onRequestExport={onRequestExport}
      />,
    )

    const selectButton = screen.getByRole('button', { name: '写真を選択' })
    expect(selectButton.querySelector('svg')).toBeInTheDocument()
    await user.click(selectButton)

    const cancelButton = screen.getByRole('button', { name: 'キャンセル' })
    expect(cancelButton).toHaveClass('danger-button--filled')
    expect(cancelButton.querySelector('svg')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'summer.jpgを選択' }))
    await user.click(screen.getByRole('button', { name: 'shared.jpgを選択' }))

    expect(screen.getByRole('button', { name: 'shared.jpgの選択を解除' })).not.toBeDisabled()
    const exportButton = screen.getByRole('button', { name: '原本を書き出す' })
    const addSharingButton = screen.getByRole('button', { name: '共有先を追加' })
    expect(exportButton.querySelector('svg')).toBeInTheDocument()
    expect(addSharingButton.querySelector('svg')).toBeInTheDocument()
    expect(addSharingButton).toBeDisabled()

    await user.click(exportButton)
    expect(onRequestExport).toHaveBeenCalledWith(['photo-1', 'photo-2'])
  })

  it('opens bulk sharing for selected photos owned by the current user', async () => {
    const user = userEvent.setup()
    const onRequestBulkSharing = vi.fn()
    render(
      <PhotoLibrary
        photos={[photo]}
        filters={{}}
        timeline={timeline}
        totalCount={1}
        loading={false}
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
        onRequestBulkSharing={onRequestBulkSharing}
      />,
    )

    await user.click(screen.getByRole('button', { name: '写真を選択' }))
    await user.click(screen.getByRole('button', { name: 'summer.jpgを選択' }))
    await user.click(screen.getByRole('button', { name: '共有先を追加' }))

    expect(onRequestBulkSharing).toHaveBeenCalledWith(['photo-1'])
  })

  it('exports selected owned photos', async () => {
    const user = userEvent.setup()
    const onRequestExport = vi.fn()
    render(
      <PhotoLibrary
        photos={[photo]}
        filters={{}}
        timeline={timeline}
        totalCount={1}
        loading={false}
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
        onRequestExport={onRequestExport}
      />,
    )

    await user.click(screen.getByRole('button', { name: '写真を選択' }))
    await user.click(screen.getByRole('button', { name: 'summer.jpgを選択' }))
    await user.click(screen.getByRole('button', { name: '原本を書き出す' }))

    expect(onRequestExport).toHaveBeenCalledWith(['photo-1'])
  })

  it('uses a separate shared selection badge position', async () => {
    const user = userEvent.setup()
    render(
      <PhotoLibrary
        photos={[{ ...photo, content_type: 'video/mp4' }]}
        filters={{}}
        timeline={timeline}
        totalCount={1}
        loading={false}
        loadingMore={false}
        hasMore={false}
        pageError={null}
        {...callbacks}
      />,
    )

    await user.click(screen.getByRole('button', { name: '写真を選択' }))
    await user.click(screen.getByRole('button', { name: 'summer.jpgを選択' }))

    const card = screen.getByRole('button', { name: 'summer.jpgの選択を解除' })
    expect(card.querySelector('.photo-badge--selection')).toHaveClass('photo-badge--bottom-left', 'photo-badge--active')
    expect(card.querySelector('.photo-badge--selection svg')).toBeInTheDocument()
    expect(card.querySelector('.photo-badge--video')).toHaveClass('photo-badge--top-right')
  })
})
