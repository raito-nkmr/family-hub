import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { PhotoActivityItem } from './api'
import { PhotoActivityPage } from './PhotoActivityPage'

const activity: PhotoActivityItem = {
  id: '00000000-0000-4000-8000-000000000001',
  event_type: 'uploaded',
  actor_user_id: '00000000-0000-4000-8000-000000000002',
  actor_username: 'family',
  operation_id: '00000000-0000-4000-8000-000000000003',
  occurred_at: '2026-07-16T03:00:00Z',
  photo: {
    id: '00000000-0000-4000-8000-000000000004',
    uploaded_by_user_id: '00000000-0000-4000-8000-000000000002',
    uploaded_by_username: 'family',
    visibility: 'shared',
    original_filename: 'new.jpg',
    content_type: 'image/jpeg',
    width: 640,
    height: 480,
    captured_at: null,
    uploaded_at: '2026-07-16T03:00:00Z',
    is_favorite: false,
  },
}

describe('PhotoActivityPage', () => {
  it('shows a grouped upload and opens its photo', async () => {
    const user = userEvent.setup()
    const onSelectPhoto = vi.fn()

    render(
      <PhotoActivityPage
        items={[activity]}
        loading={false}
        loadingMore={false}
        hasMore={false}
        error={null}
        onRefresh={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectPhoto={onSelectPhoto}
      />,
    )

    expect(screen.getByText('familyさんが写真を1枚追加しました')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'new.jpgを開く' }))
    expect(onSelectPhoto).toHaveBeenCalledWith(activity.photo)
  })

  it('shows an empty state when there is no recent activity', () => {
    render(
      <PhotoActivityPage
        items={[]}
        loading={false}
        loadingMore={false}
        hasMore={false}
        error={null}
        onRefresh={vi.fn()}
        onLoadMore={vi.fn()}
        onSelectPhoto={vi.fn()}
      />,
    )

    expect(screen.getByText('新着写真はありません')).toBeInTheDocument()
  })
})
