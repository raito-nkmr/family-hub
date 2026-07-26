# Current Web Push Specification

## Current conclusion

Family Hub provides a settings UI that requests notification permission and registers a `PushManager` subscription with
the backend. It also includes a notification outbox, a delivery worker, and Service Worker logic for displaying
notifications and opening the relevant in-app screen. Users can enable or disable notifications for the current device
and change notification categories from the Account screen under “Other”.

On iPhone and iPad, Web Push requires iOS or iPadOS 16.4 or later, Family Hub to be added to the Home Screen, and the
app to be launched as a standalone web app. Permission and Push subscription requests must also be triggered by a direct
user action, such as tapping an in-app button. Family Hub starts this action from the “Enable notifications” button on
the Account screen. When Push APIs are unavailable in a normal Safari tab, the UI shows instructions for adding the app
to the Home Screen.

## Implemented flow

The implemented flow is:

1. In a production build, the browser registers `/sw.js` as a Service Worker.
2. The user launches standalone Family Hub from the Home Screen and taps the enable-notifications button.
3. The frontend requests notification permission and creates a Push subscription using the public VAPID key.
4. The endpoint and encryption keys are registered with `POST /api/v1/notifications/subscriptions`. Notification categories can be changed afterward.
5. A photo-sharing or shopping-item transaction, or the cleaning-due command, creates a notification outbox entry.
6. `python -m app.commands.send_notifications` claims outbox entries and sends encrypted notifications to the Web Push provider.
7. The Service Worker handles the `push` event, displays the notification, increments the device-local unread count, and shows a badge on supported app icons.
8. Opening a notification clears the badge and focuses the relevant Family Hub screen, opening it if necessary. Normal app startup also clears the badge.

## Notification categories and defaults

| Category | Outbox trigger | Potential recipients | Default | Destination |
| --- | --- | --- | --- | --- |
| Photo shared | An upload with a group share, or adding a new group to an existing share | Members of the newly shared group, excluding the actor | Enabled | `/photos/new` |
| Cleaning due | The cleaning-due command finds an active task that is due | All members of the relevant group | Enabled | `/cleaning` |
| Shopping item added | An unpurchased item is added to a group | Group members, excluding the actor | Disabled | `/shopping` |

Notification messages are localized templates selected from the subscription's `en` or `ja` language. They do not
include photo names, cleaning-task names, or shopping-item names. The same operation does not create duplicate outbox
entries for the same user. The settings UI saves the enabled state of all three categories together.

## Subscriptions and login sessions

A Push subscription is associated with both a user and the login session that registered it. Delivery targets must belong
to an active user and must not be associated with a revoked, absolutely expired, idle-expired, or pre-password-change
session. Devices whose sessions were invalidated by logout or a password change do not receive notifications.

The number of subscriptions per user is limited by `PUSH_MAX_SUBSCRIPTIONS_PER_USER`, which defaults to 10. The unsubscribe
API can delete only subscriptions belonging to the current user and current login session. Subscriptions for which the
provider returns `404` or `410` are deleted by the delivery worker as expired.

## Delivery, retries, and display

Photo sharing and shopping-item additions write their outbox entries in the same database transaction as the underlying
change. Cleaning due dates are evaluated by `python -m app.commands.enqueue_due_cleaning_notifications`, which prevents
duplicate entries for the same task and due date. The delivery systemd timer runs every minute, and the cleaning-due
timer runs every hour. The production runbook keeps both timers disabled until VAPID configuration and real-device
validation are complete.

Delivery state is stored per subscription. If only some devices fail temporarily, successful devices are not retried;
only unsuccessful devices are retried. The delay grows exponentially with the outbox attempt count. A temporary error
ends in failure after five attempts for a device. An outbox entry is marked processed when there are no eligible
subscriptions or when the user has disabled the relevant category.

The Service Worker receives a title, body, destination, and deduplication tag in the Push payload and displays the
notification immediately. A click destination must use the same origin. External URLs, URLs containing credentials, and
invalid URLs are replaced with the application root. On devices supporting the Badging API, each Push increments a
device-local unread count up to 999. The count is shown on the Home Screen app icon and cleared when the PWA starts or a
notification is opened. It is not server-side unread state; it is the number of notifications received on that device
since the app was last opened. The badge is not shown when disabled in the operating-system settings. Notification action
buttons and a notification history screen are not implemented.

## API and configuration

All notification APIs require authentication, and mutation APIs also require CSRF validation.

| API | Purpose |
| --- | --- |
| `GET /api/v1/notifications/config` | Returns Web Push availability, the public VAPID key, the current session's subscription IDs, and notification preferences |
| `POST /api/v1/notifications/subscriptions` | Registers a Push subscription for the current login session |
| `DELETE /api/v1/notifications/subscriptions/{id}` | Removes a Push subscription from the current login session |
| `PUT /api/v1/notifications/preferences` | Updates all three category preferences for the user |

Web Push is enabled only when `PUSH_VAPID_PUBLIC_KEY`, `PUSH_VAPID_PRIVATE_KEY_FILE`, and `PUSH_VAPID_SUBJECT` are all
configured. Store the private key outside the repository. Subscription endpoints must use HTTPS, and only provider hosts
listed in `PUSH_ALLOWED_ENDPOINT_HOSTS` are accepted. The subscription API does not connect to endpoints; only the
delivery worker performs outbound communication.

## Verification status and remaining work

Automated tests cover API registration, CSRF, the endpoint allowlist, subscription limits, the preference schema,
browser subscription registration and removal, the settings UI, recipient generation, safe click destinations, badge
count normalization, and worker claiming and per-device retries. Worker PostgreSQL integration tests run in environments
with `TEST_DATABASE_URL` configured.

On July 20, 2026, VAPID was configured in the public test environment and a subscription was registered from the iPhone
Home Screen PWA. A shopping-item addition by another user was verified end to end through the outbox, Web Push provider,
and Service Worker, including a background Japanese notification and app-icon badge. Both the outbox and per-device
delivery were `sent`, and the delivery and cleaning-due timers were `enabled` and `active`.

The following acceptance checks remain:

- Navigation to the destination screen by clicking a notification
- Behavior when Focus is enabled, or notifications and badges are disabled in iPhone settings

For Apple's current requirements, see [Apple's Web Push documentation](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
and [WebKit's iOS and iPadOS guidance](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

日本語版: [web-push.ja.md](./web-push.ja.md)
