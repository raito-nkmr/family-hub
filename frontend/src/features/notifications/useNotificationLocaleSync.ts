import { useEffect, useRef } from 'react'
import { isUnauthorizedError } from '../../shared/api/errors'
import type { AppLanguage } from '../../i18n'
import { updateNotificationLocale } from './api'

interface UseNotificationLocaleSyncOptions {
  locale: AppLanguage
  onUnauthorized: () => void
}

export function useNotificationLocaleSync({ locale, onUnauthorized }: UseNotificationLocaleSyncOptions) {
  const previousLocaleRef = useRef(locale)
  const latestLocaleRef = useRef(locale)
  const syncChainRef = useRef(Promise.resolve())

  useEffect(() => {
    latestLocaleRef.current = locale
    if (previousLocaleRef.current === locale) return
    previousLocaleRef.current = locale
    const requestedLocale = locale
    syncChainRef.current = syncChainRef.current
      .catch(() => undefined)
      .then(async () => {
        if (latestLocaleRef.current !== requestedLocale) return
        try {
          await updateNotificationLocale(requestedLocale)
        } catch (error) {
          if (isUnauthorizedError(error) && latestLocaleRef.current === requestedLocale) onUnauthorized()
        }
      })
  }, [locale, onUnauthorized])
}
