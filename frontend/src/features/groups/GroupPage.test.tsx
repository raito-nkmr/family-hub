import { render, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/client'
import { createAppWrapper } from '../../test/renderWithAppProviders'
import { getGroups } from './api'
import { GroupPage } from './GroupPage'

vi.mock('./api', () => ({
  addGroupMember: vi.fn(),
  createGroup: vi.fn(),
  getGroup: vi.fn(),
  getGroupMemberCandidates: vi.fn(),
  getGroups: vi.fn(),
  removeGroupMember: vi.fn(),
  updateGroupMemberRole: vi.fn(),
}))

describe('GroupPage', () => {
  it('returns control to the app when the session expires', async () => {
    vi.mocked(getGroups).mockRejectedValue(new ApiError(401, 'expired'))
    const onUnauthorized = vi.fn()

    render(<GroupPage currentUserId="current-user" onUnauthorized={onUnauthorized} />, {
      wrapper: createAppWrapper(),
    })

    await waitFor(() => expect(onUnauthorized).toHaveBeenCalledOnce())
  })
})
