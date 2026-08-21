import { useTranslation } from 'react-i18next'
import type { NotificationType } from '../../shared/api/generated'
import { PageMessage } from '../../shared/ui/PageMessage'
import { ApkInstallIcon, NotificationIcon, NotificationsActiveIcon, SaveIcon } from '../../shared/ui/icons'
import { useNotificationSettings } from './useNotificationSettings'

interface NotificationSettingsProps {
  showInstallGuide: boolean
  onShowInstallGuide: () => void
  onUnauthorized: () => void
}

const NOTIFICATION_TYPES: NotificationType[] = ['photo_shared', 'chore_due', 'shopping_added']

export function NotificationSettings({
  showInstallGuide,
  onShowInstallGuide,
  onUnauthorized,
}: NotificationSettingsProps) {
  const { t, i18n } = useTranslation()
  const settings = useNotificationSettings({
    locale: i18n.resolvedLanguage === 'ja' ? 'ja' : 'en',
    onUnauthorized,
  })
  const busy = settings.busyAction !== null

  const statusKey = settings.loading
    ? 'notifications.statusLoading'
    : settings.error === 'load'
      ? 'notifications.statusLoadFailed'
      : !settings.config?.enabled
        ? 'notifications.statusUnavailable'
        : settings.permission === 'unsupported'
          ? 'notifications.statusUnsupported'
          : settings.permission === 'denied'
            ? 'notifications.statusDenied'
            : settings.subscribed
              ? 'notifications.statusEnabled'
              : 'notifications.statusDisabled'

  return (
    <section className="account-panel account-panel--notifications" aria-labelledby="notification-settings-heading">
      <div className="notification-settings__heading">
        <span className="notification-settings__icon">
          <NotificationIcon />
        </span>
        <div>
          <h2 id="notification-settings-heading">{t('notifications.title')}</h2>
          <p>{t('notifications.description')}</p>
        </div>
      </div>

      <p className="notification-settings__status" aria-live="polite">
        {t(statusKey)}
      </p>

      {settings.error && <PageMessage>{t(`notifications.errors.${settings.error}`)}</PageMessage>}

      {!settings.loading && settings.config?.enabled && settings.permission !== 'unsupported' && (
        <div className="notification-settings__actions">
          {settings.subscribed ? (
            <button
              className="danger-button icon-button"
              type="button"
              disabled={busy}
              onClick={() => void settings.disable()}
            >
              <NotificationIcon />
              {t(settings.busyAction === 'unsubscribe' ? 'notifications.disabling' : 'notifications.disable')}
            </button>
          ) : (
            <button
              className="success-button icon-button"
              type="button"
              disabled={busy || settings.permission === 'denied'}
              onClick={() => void settings.enable()}
            >
              <NotificationsActiveIcon />
              {t(settings.busyAction === 'subscribe' ? 'notifications.enabling' : 'notifications.enable')}
            </button>
          )}
        </div>
      )}

      {!settings.loading && showInstallGuide && settings.permission === 'unsupported' && (
        <button
          className="secondary-button icon-button notification-settings__install"
          type="button"
          onClick={onShowInstallGuide}
        >
          <ApkInstallIcon />
          {t('pwa.showGuide')}
        </button>
      )}

      {settings.subscribed && (
        <fieldset className="notification-preferences" disabled={busy}>
          <legend>{t('notifications.preferencesTitle')}</legend>
          <p>{t('notifications.preferencesDescription')}</p>
          {NOTIFICATION_TYPES.map((notificationType) => {
            const preference = settings.preferences.find((item) => item.notification_type === notificationType)
            return (
              <label key={notificationType} className="notification-preferences__item">
                <span>
                  <strong>{t(`notifications.types.${notificationType}.title`)}</strong>
                  <small>{t(`notifications.types.${notificationType}.description`)}</small>
                </span>
                <input
                  type="checkbox"
                  checked={preference?.enabled ?? false}
                  onChange={(event) => settings.setPreference(notificationType, event.target.checked)}
                />
              </label>
            )
          })}
          <button className="success-button icon-button" type="button" onClick={() => void settings.savePreferences()}>
            <SaveIcon />
            {t(settings.busyAction === 'preferences' ? 'common.saving' : 'notifications.savePreferences')}
          </button>
        </fieldset>
      )}
    </section>
  )
}
