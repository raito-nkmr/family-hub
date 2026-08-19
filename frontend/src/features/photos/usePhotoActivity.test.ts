import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getPhotoActivity, markPhotoActivitySeen } from './api'
import { usePhotoActivity } from './usePhotoActivity'
import { createAppWrapper } from '../../test/renderWithAppProviders'

vi.mock('./api', () => ({
  getPhotoActivity: vi.fn(),
  markPhotoActivitySeen: vi.fn(),
}))

describe('usePhotoActivity', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('marks the latest event seen when the recent tab becomes active', async () => {
    vi.mocked(getPhotoActivity).mockResolvedValue({
      items: [
        {
          id: 'event-1',
          event_type: 'uploaded',
          actor_user_id: 'user-2',
          actor_username: 'family',
          operation_id: 'operation-1',
          occurred_at: '2026-07-16T03:00:00Z',
          photo: {
            id: 'photo-1',
            uploaded_by_user_id: 'user-2',
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
        },
      ],
      next_cursor: null,
      unseen_count: 1,
    })
    vi.mocked(markPhotoActivitySeen).mockResolvedValue()
    const onUnauthorized = vi.fn()
    const { result, rerender } = renderHook(
      ({ active, userId }) => usePhotoActivity({ enabled: true, userId, active, onUnauthorized }),
      { initialProps: { active: false, userId: 'user-1' }, wrapper: createAppWrapper() },
    )

    await waitFor(() => expect(result.current.unseenCount).toBe(1))
    rerender({ active: true, userId: 'user-1' })

    await waitFor(() => expect(markPhotoActivitySeen).toHaveBeenCalledWith('event-1', expect.anything()))
    await waitFor(() => expect(result.current.unseenCount).toBe(0))
  })

  it('hides the previous user activity immediately when the session changes', async () => {
    vi.mocked(getPhotoActivity).mockResolvedValueOnce({
      items: [],
      next_cursor: null,
      unseen_count: 3,
    })
    let resolveNext: ((value: Awaited<ReturnType<typeof getPhotoActivity>>) => void) | undefined
    vi.mocked(getPhotoActivity).mockImplementationOnce(() => new Promise((resolve) => (resolveNext = resolve)))
    const { result, rerender } = renderHook(
      ({ userId }) => usePhotoActivity({ enabled: true, userId, active: false, onUnauthorized: vi.fn() }),
      { initialProps: { userId: 'user-1' }, wrapper: createAppWrapper() },
    )
    await waitFor(() => expect(result.current.unseenCount).toBe(3))

    rerender({ userId: 'user-2' })

    expect(result.current.unseenCount).toBe(0)
    expect(result.current.items).toEqual([])
    resolveNext?.({ items: [], next_cursor: null, unseen_count: 0 })
    await waitFor(() => expect(result.current.loading).toBe(false))
  })

  it('does not retry a failed seen update automatically and supports a manual retry', async () => {
    vi.mocked(getPhotoActivity).mockResolvedValue({
      items: [
        {
          id: 'event-1',
          event_type: 'uploaded',
          actor_user_id: 'user-2',
          actor_username: 'family',
          operation_id: 'operation-1',
          occurred_at: '2026-07-16T03:00:00Z',
          photo: {
            id: 'photo-1',
            uploaded_by_user_id: 'user-2',
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
        },
      ],
      next_cursor: null,
      unseen_count: 1,
    })
    vi.mocked(markPhotoActivitySeen).mockRejectedValueOnce(new Error('temporary failure')).mockResolvedValueOnce()
    const { result } = renderHook(
      () => usePhotoActivity({ enabled: true, userId: 'user-1', active: true, onUnauthorized: vi.fn() }),
      { wrapper: createAppWrapper() },
    )

    await waitFor(() => expect(result.current.markSeenError).toBe('新着写真を既読にできませんでした。'))
    expect(markPhotoActivitySeen).toHaveBeenCalledTimes(1)

    act(() => result.current.retryMarkSeen())

    await waitFor(() => expect(markPhotoActivitySeen).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(result.current.markSeenError).toBeNull())
  })
})
