import { describe, expect, it } from 'vitest'
import { decodeVapidPublicKey, serializePushSubscription } from './webPush'

describe('Web Push helpers', () => {
  it('decodes a URL-safe VAPID public key', () => {
    expect([...decodeVapidPublicKey('AQID-_8')]).toEqual([1, 2, 3, 251, 255])
  })

  it('serializes the browser subscription for the backend', () => {
    const subscription = {
      toJSON: () => ({
        endpoint: 'https://web.push.apple.com/example',
        keys: { p256dh: 'public-key', auth: 'auth-key' },
      }),
    } as unknown as PushSubscription

    expect(serializePushSubscription(subscription, 'ja')).toEqual({
      endpoint: 'https://web.push.apple.com/example',
      keys: { p256dh: 'public-key', auth: 'auth-key' },
      locale: 'ja',
    })
  })

  it('rejects an incomplete browser subscription', () => {
    const subscription = {
      toJSON: () => ({ endpoint: 'https://web.push.apple.com/example' }),
    } as unknown as PushSubscription
    expect(() => serializePushSubscription(subscription, 'en')).toThrow('missing required fields')
  })
})
