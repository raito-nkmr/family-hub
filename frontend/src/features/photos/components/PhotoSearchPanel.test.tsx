import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PhotoSearchPanel } from './PhotoSearchPanel'

describe('PhotoSearchPanel', () => {
  it('opens the compact search controls and collapses them after filtering', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    render(<PhotoSearchPanel filters={{ q: '旅行' }} timeline={null} disabled={false} onSearch={onSearch} />)

    const toggle = screen.getByRole('button', { name: '検索条件を表示' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByText('1件適用中')).toBeInTheDocument()

    await user.click(toggle)
    expect(screen.getByRole('button', { name: '検索条件を閉じる' })).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('button', { name: '絞り込む' }))
    expect(onSearch).toHaveBeenCalledWith(expect.objectContaining({ q: '旅行' }))
    expect(screen.getByRole('button', { name: '検索条件を表示' })).toHaveAttribute('aria-expanded', 'false')
  })

  it('keeps visible search fields aligned when a timeline month is selected', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    render(
      <PhotoSearchPanel
        filters={{ q: '旅行', favorite: true }}
        timeline={{ year: 2026, months: [{ month: '2026-07', count: 2 }] }}
        disabled={false}
        onSearch={onSearch}
      />,
    )

    await user.click(screen.getByRole('button', { name: /7月/ }))

    expect(onSearch).toHaveBeenCalledWith({
      q: '旅行',
      favorite: true,
      dateFrom: '2026-07-01',
      dateTo: '2026-07-31',
    })
    expect(screen.getByDisplayValue('旅行')).toBeInTheDocument()
    expect(screen.getByDisplayValue('2026-07-01')).toBeInTheDocument()
  })

  it('shows uploader and shared-group options and submits their URL-backed filters', async () => {
    const user = userEvent.setup()
    const onSearch = vi.fn()
    render(
      <PhotoSearchPanel
        filters={{}}
        timeline={null}
        searchOptions={{
          uploaders: [{ id: 'user-1', name: 'owner' }],
          groups: [{ id: 'group-1', name: 'Family' }],
        }}
        disabled={false}
        onSearch={onSearch}
      />,
    )

    await user.click(screen.getByRole('button', { name: '検索条件を表示' }))
    await user.selectOptions(screen.getByLabelText('投稿者'), 'user-1')
    await user.selectOptions(screen.getByLabelText('共有グループ'), 'group-1')
    await user.click(screen.getByRole('button', { name: '絞り込む' }))

    expect(onSearch).toHaveBeenCalledWith({ uploaderId: 'user-1', sharingGroupId: 'group-1' })
  })

  it('synchronizes local fields when URL-backed filters change', async () => {
    const searchOptions = { uploaders: [{ id: 'user-1', name: 'owner' }], groups: [] }
    const { rerender } = render(
      <PhotoSearchPanel
        filters={{ q: '旅行' }}
        searchOptions={searchOptions}
        timeline={null}
        disabled={false}
        onSearch={vi.fn()}
      />,
    )

    expect(screen.getByRole('searchbox')).toHaveValue('旅行')
    rerender(
      <PhotoSearchPanel
        filters={{ q: '新着', uploaderId: 'user-1' }}
        searchOptions={searchOptions}
        timeline={null}
        disabled={false}
        onSearch={vi.fn()}
      />,
    )

    await screen.findByDisplayValue('新着')
    expect(screen.getByLabelText('投稿者')).toHaveValue('user-1')
  })

  it('does not count fixed album picker filters as user-applied conditions', () => {
    render(
      <PhotoSearchPanel
        filters={{ excludeAlbumId: 'album-1', sharingGroupId: 'group-1' }}
        timeline={null}
        showSharingGroupFilter={false}
        disabled={false}
        onSearch={vi.fn()}
      />,
    )

    expect(screen.queryByText(/件適用中/)).not.toBeInTheDocument()
  })
})
