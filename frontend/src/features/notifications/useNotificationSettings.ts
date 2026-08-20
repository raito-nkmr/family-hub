import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  NotificationConfigResponse,
  NotificationPreferenceItem,
  NotificationPreferenceUpdate,
  NotificationType,
} from '../../shared/api/generated'
import { ApiError } from '../../shared/api/client'
import { isAbortError, isUnauthorizedError } from '../../shared/api/errors'
import { queryKeys } from '../../shared/api/queryKeys'
import { useUnauthorizedError } from '../../shared/api/useUnauthorizedError'
import type { AppLanguage } from '../../i18n'
import {
  createPushSubscription,
  deletePushSubscription,
  getNotificationConfig,
  updateNotificationPreferences,
} from './api'
import {
  decodeVapidPublicKey,
  getNotificationServiceWorkerRegistration,
  hasPushManager,
  isWebPushSupported,
  serializePushSubscription,
} from './webPush'

export type NotificationSettingsError =
  | 'load'
  | 'permissionDenied'
  | 'serviceWorkerUnavailable'
  | 'subscriptionLimit'
  | 'subscribe'
  | 'unsubscribe'
  | 'preferences'

type BusyAction = 'subscribe' | 'unsubscribe' | 'preferences' | null

interface UseNotificationSettingsOptions {
  locale: AppLanguage
  onUnauthorized: () => void
}

export function useNotificationSettings({ locale, onUnauthorized }: UseNotificationSettingsOptions) {
  const queryClient = useQueryClient()
  const [preferenceOverrides, setPreferenceOverrides] = useState<NotificationPreferenceItem[] | null>(null)
  const [browserSubscribed, setBrowserSubscribed] = useState(false)
  const [browserReady, setBrowserReady] = useState(false)
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(() =>
    isWebPushSupported() ? Notification.permission : 'unsupported',
  )
  const [busyAction, setBusyAction] = useState<BusyAction>(null)
  const [error, setError] = useState<NotificationSettingsError | null>(null)
  const registrationRef = useRef<ServiceWorkerRegistration | null>(null)
  const configQuery = useQuery({
    queryKey: queryKeys.notificationConfig,
    queryFn: ({ signal }) => getNotificationConfig(signal),
  })
  const createMutation = useMutation({ mutationFn: createPushSubscription })
  const deleteMutation = useMutation({ mutationFn: deletePushSubscription })
  const preferencesMutation = useMutation({ mutationFn: updateNotificationPreferences })
  const unauthorizedError = [
    configQuery.error,
    createMutation.error,
    deleteMutation.error,
    preferencesMutation.error,
  ].find(isUnauthorizedError)
  useUnauthorizedError(unauthorizedError, onUnauthorized)
  const config = configQuery.data ?? null
  const preferences = preferenceOverrides ?? config?.preferences ?? []

  useEffect(() => {
    if (!configQuery.isSuccess) return
    let active = true
    const loadBrowserState = async () => {
      if (!isWebPushSupported()) {
        setPermission('unsupported')
        setBrowserSubscribed(false)
        setBrowserReady(true)
        return
      }
      setPermission(Notification.permission)
      try {
        const registration = await getNotificationServiceWorkerRegistration()
        if (!active) return
        if (!registration || !hasPushManager(registration)) {
          setPermission('unsupported')
          setBrowserSubscribed(false)
          return
        }
        registrationRef.current = registration
        const subscription = await registration.pushManager.getSubscription()
        if (active) setBrowserSubscribed(Boolean(subscription))
      } catch (loadError) {
        if (!isAbortError(loadError)) setError('load')
      } finally {
        if (active) setBrowserReady(true)
      }
    }
    void loadBrowserState()
    return () => {
      active = false
    }
  }, [configQuery.isSuccess])

  const enable = async () => {
    if (!config?.enabled || !config.vapid_public_key || !isWebPushSupported()) return
    setBusyAction('subscribe')
    setError(null)
    let createdSubscription: PushSubscription | null = null
    let serverSubscriptionCreated = false
    try {
      const nextPermission =
        Notification.permission === 'default' ? await Notification.requestPermission() : Notification.permission
      setPermission(nextPermission)
      if (nextPermission !== 'granted') {
        setError('permissionDenied')
        return
      }
      const registration = registrationRef.current ?? (await getNotificationServiceWorkerRegistration()) ?? null
      registrationRef.current = registration
      if (!registration || !hasPushManager(registration)) {
        setPermission('unsupported')
        setError('serviceWorkerUnavailable')
        return
      }
      let subscription = await registration.pushManager.getSubscription()
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: decodeVapidPublicKey(config.vapid_public_key),
        })
        createdSubscription = subscription
      }
      const response = await createMutation.mutateAsync(serializePushSubscription(subscription, locale))
      serverSubscriptionCreated = true
      for (const subscriptionId of config.subscription_ids) {
        if (subscriptionId !== response.id) await deleteMutation.mutateAsync(subscriptionId)
      }
      queryClient.setQueryData<NotificationConfigResponse>(queryKeys.notificationConfig, (current) =>
        current ? { ...current, subscription_ids: [response.id] } : current,
      )
      setBrowserSubscribed(true)
    } catch (subscribeError) {
      if (createdSubscription && !serverSubscriptionCreated) await createdSubscription.unsubscribe().catch(() => false)
      if (!isUnauthorizedError(subscribeError)) {
        const isSubscriptionLimit =
          subscribeError instanceof ApiError &&
          subscribeError.status === 409 &&
          (subscribeError.code === 'push_subscription_limit_reached' || subscribeError.code === undefined)
        setError(isSubscriptionLimit ? 'subscriptionLimit' : 'subscribe')
      }
    } finally {
      setBusyAction(null)
    }
  }

  const disable = async () => {
    if (!config) return
    setBusyAction('unsubscribe')
    setError(null)
    try {
      for (const subscriptionId of config.subscription_ids) await deleteMutation.mutateAsync(subscriptionId)
      const subscription = await registrationRef.current?.pushManager.getSubscription()
      await subscription?.unsubscribe()
      queryClient.setQueryData<NotificationConfigResponse>(queryKeys.notificationConfig, (current) =>
        current ? { ...current, subscription_ids: [] } : current,
      )
      setBrowserSubscribed(false)
    } catch (unsubscribeError) {
      if (!isUnauthorizedError(unsubscribeError)) setError('unsubscribe')
    } finally {
      setBusyAction(null)
    }
  }

  const setPreference = (notificationType: NotificationType, enabled: boolean) => {
    setPreferenceOverrides(
      preferences.map((item) => (item.notification_type === notificationType ? { ...item, enabled } : item)),
    )
  }

  const savePreferences = async () => {
    if (preferences.length !== 3) return
    setBusyAction('preferences')
    setError(null)
    try {
      const items = preferences as NotificationPreferenceUpdate['items']
      const saved = await preferencesMutation.mutateAsync(items)
      setPreferenceOverrides(null)
      queryClient.setQueryData<NotificationConfigResponse>(queryKeys.notificationConfig, (current) =>
        current ? { ...current, preferences: saved } : current,
      )
    } catch (preferenceError) {
      if (!isUnauthorizedError(preferenceError)) setError('preferences')
    } finally {
      setBusyAction(null)
    }
  }

  return {
    config,
    preferences,
    permission,
    loading: configQuery.isPending || (configQuery.isSuccess && !browserReady),
    busyAction,
    error: error ?? (configQuery.error && !isUnauthorizedError(configQuery.error) ? 'load' : null),
    subscribed: browserSubscribed && Boolean(config?.subscription_ids.length),
    enable,
    disable,
    setPreference,
    savePreferences,
  }
}
