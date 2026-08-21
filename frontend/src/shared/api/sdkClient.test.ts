import { describe, expect, it } from 'vitest'
import { sdkData } from './sdkClient'

describe('sdkData', () => {
  it('returns generated SDK data for a successful response', async () => {
    const response = new Response(JSON.stringify({ value: 1 }), { status: 200 })

    await expect(sdkData(Promise.resolve({ data: { value: 1 }, response }))).resolves.toEqual({ value: 1 })
  })

  it('normalizes generated SDK failures to the application ApiError', async () => {
    const response = new Response(JSON.stringify({ detail: 'forbidden' }), { status: 403 })

    await expect(sdkData(Promise.resolve({ error: { detail: 'forbidden' }, response }))).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'API request failed with status 403',
    })
  })

  it('preserves a machine-readable error code from the API detail', async () => {
    const response = new Response(JSON.stringify({ detail: { code: 'push_subscription_endpoint_conflict' } }), {
      status: 409,
    })

    await expect(
      sdkData(
        Promise.resolve({
          error: { detail: { code: 'push_subscription_endpoint_conflict' } },
          response,
        }),
      ),
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      code: 'push_subscription_endpoint_conflict',
    })
  })
})
