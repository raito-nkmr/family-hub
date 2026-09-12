import { beforeEach, describe, expect, it, vi } from 'vitest'
import { client } from '../../shared/api/generated/client.gen'
import { addGroupMember, getGroups } from './api'

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

  it('adds a group member through the generated SDK', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          user_id: 'user-2',
          username: 'member',
          is_active: true,
          role: 'member',
          joined_at: '2026-07-15T00:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await expect(addGroupMember('group-1', 'user-2', 'member')).resolves.toMatchObject({
      user_id: 'user-2',
      username: 'member',
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    const request = fetchMock.mock.calls[0][0] as Request
    expect(request.url).toContain('/api/v1/groups/group-1/members')
    await expect(request.json()).resolves.toMatchObject({ user_id: 'user-2', role: 'member' })
  })
})
