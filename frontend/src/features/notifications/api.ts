import type {
  NotificationConfigResponse,
  NotificationPreferenceItem,
  NotificationPreferenceUpdate,
  PushSubscriptionCreate,
  PushSubscriptionResponse,
} from '../../shared/api/generated'
import {
  createPushSubscriptionApiV1NotificationsSubscriptionsPost,
  deletePushSubscriptionApiV1NotificationsSubscriptionsSubscriptionIdDelete,
  getNotificationConfigApiV1NotificationsConfigGet,
  updatePushSubscriptionLocaleApiV1NotificationsSubscriptionsLocalePut,
  updateNotificationPreferencesApiV1NotificationsPreferencesPut,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export function getNotificationConfig(signal?: AbortSignal): Promise<NotificationConfigResponse> {
  return sdkData(getNotificationConfigApiV1NotificationsConfigGet({ signal }))
}

export function createPushSubscription(body: PushSubscriptionCreate): Promise<PushSubscriptionResponse> {
  return sdkData(createPushSubscriptionApiV1NotificationsSubscriptionsPost({ body }))
}

export function deletePushSubscription(subscriptionId: string): Promise<void> {
  return sdkData(
    deletePushSubscriptionApiV1NotificationsSubscriptionsSubscriptionIdDelete({
      path: { subscription_id: subscriptionId },
    }),
  )
}

export function updateNotificationLocale(locale: 'en' | 'ja'): Promise<void> {
  return sdkData(updatePushSubscriptionLocaleApiV1NotificationsSubscriptionsLocalePut({ body: { locale } }))
}

export function updateNotificationPreferences(
  items: NotificationPreferenceUpdate['items'],
): Promise<NotificationPreferenceItem[]> {
  return sdkData(updateNotificationPreferencesApiV1NotificationsPreferencesPut({ body: { items } }))
}
