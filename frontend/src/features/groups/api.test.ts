import { beforeEach, describe, expect, it, vi } from 'vitest'
import { client } from '../../shared/api/generated/client.gen'
import { getGroups, inviteGroupMember } from './api'

describe('generated groups API', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    fetchMock.mockReset()
    client.setConfig({
      baseUrl: window.location.origin,
      fetch: fetchMock,
      credentials: 'same-origin',
      responseStyle: 'fields',
      throwOnError: false,
    })
  })

  it('uses the generated SDK with same-origin credentials', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ items: [{ id: 'group-1', name: 'Family' }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(getGroups()).resolves.toEqual([{ id: 'group-1', name: 'Family' }])

    const request = fetchMock.mock.calls[0][0] as Request
    expect(request.url).toBe('http://localhost:3000/api/v1/groups')
    expect(request.credentials).toBe('same-origin')
  })

  it('returns the invitation response without fetching group details', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'invitation-1',
          group_id: 'group-1',
          group_name: 'Family',
          invitee_user_id: 'user-2',
          invitee_username: 'member',
          role: 'member',
          status: 'pending',
          created_at: '2026-07-15T00:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await expect(inviteGroupMember('group-1', 'user-2', 'member')).resolves.toMatchObject({
      id: 'invitation-1',
      group_id: 'group-1',
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    expect((fetchMock.mock.calls[0][0] as Request).url).toContain('/api/v1/groups/group-1/membership-invitations')
  })
})
