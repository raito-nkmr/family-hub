import type { PushSubscriptionCreate } from '../../shared/api/generated'
import type { AppLanguage } from '../../i18n'

export function isWebPushSupported(): boolean {
  return 'Notification' in window && 'serviceWorker' in navigator
}

export function hasPushManager(
  registration: ServiceWorkerRegistration,
): registration is ServiceWorkerRegistration & { pushManager: PushManager } {
  return 'pushManager' in registration && registration.pushManager !== undefined
}

export async function getNotificationServiceWorkerRegistration(): Promise<ServiceWorkerRegistration | undefined> {
  const existing = await navigator.serviceWorker.getRegistration()
  if (existing || !import.meta.env.PROD) return existing
  return navigator.serviceWorker.register('/sw.js')
}

export function decodeVapidPublicKey(value: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (value.length % 4)) % 4)
  const base64 = (value + padding).replaceAll('-', '+').replaceAll('_', '/')
  const decoded = window.atob(base64)
  return Uint8Array.from(decoded, (character) => character.charCodeAt(0))
}

export function serializePushSubscription(subscription: PushSubscription, locale: AppLanguage): PushSubscriptionCreate {
  const serialized = subscription.toJSON()
  if (!serialized.endpoint || !serialized.keys?.p256dh || !serialized.keys.auth) {
    throw new Error('Push subscription is missing required fields')
  }
  return {
    endpoint: serialized.endpoint,
    keys: { p256dh: serialized.keys.p256dh, auth: serialized.keys.auth },
    locale,
  }
}
