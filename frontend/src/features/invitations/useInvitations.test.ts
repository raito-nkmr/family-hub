import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createInvitation, getInvitations, type CreatedInvitation } from './api'
import { useInvitations } from './useInvitations'
import { createAppWrapper } from '../../test/renderWithAppProviders'

vi.mock('./api', () => ({
  createInvitation: vi.fn(),
  getInvitations: vi.fn(),
  removeInvitationHistory: vi.fn(),
  revokeInvitation: vi.fn(),
}))

const createdInvitation: CreatedInvitation = {
  id: 'invitation-1',
  username: 'family-member',
  created_by_username: 'owner',
  created_at: '2026-07-15T00:00:00Z',
  expires_at: '2026-07-16T00:00:00Z',
  status: 'pending',
  token: 'invitation-token',
}

describe('useInvitations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getInvitations).mockResolvedValue([])
  })

  it('keeps the one-time token after creating an invitation', async () => {
    vi.mocked(createInvitation).mockResolvedValue(createdInvitation)
    const onUnauthorized = vi.fn()
    const { result } = renderHook(() => useInvitations({ onUnauthorized }), { wrapper: createAppWrapper() })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(() => result.current.create('family-member'))

    expect(result.current.invitations).toEqual([
      {
        id: 'invitation-1',
        username: 'family-member',
        created_by_username: 'owner',
        created_at: '2026-07-15T00:00:00Z',
        expires_at: '2026-07-16T00:00:00Z',
        status: 'pending',
      },
    ])
    expect(result.current.createdInvitation?.token).toBe('invitation-token')
  })
})
