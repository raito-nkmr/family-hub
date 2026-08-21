import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.public import User, UserSession
from app.features.notifications.models import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationOutbox,
    NotificationOutboxStatus,
    NotificationPreference,
    NotificationType,
    PushSubscription,
)
from app.features.notifications.service import DEFAULT_PREFERENCES

MESSAGES = {
    "en": {
        NotificationType.PHOTO_SHARED: ("Family Hub", "New photos were shared with your family."),
        NotificationType.CHORE_DUE: ("Family Hub", "A chore task is due."),
        NotificationType.SHOPPING_ADDED: ("Family Hub", "The shopping list was updated."),
    },
    "ja": {
        NotificationType.PHOTO_SHARED: ("Family Hub", "家族に新しい写真が共有されました。"),
        NotificationType.CHORE_DUE: ("Family Hub", "期限になった家事タスクがあります。"),
        NotificationType.SHOPPING_ADDED: ("Family Hub", "買い物リストが更新されました。"),
    },
}
logger = logging.getLogger(__name__)


class NotificationWorker:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def process(self, *, limit: int = 100) -> int:
        self._recover_stale_claims()
        processed = 0
        for _ in range(limit):
            item = self._claim_one()
            if item is None:
                break
            self._deliver(item)
            processed += 1
        return processed

    def _claim_one(self) -> NotificationOutbox | None:
        item = self._session.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status == NotificationOutboxStatus.PENDING,
                NotificationOutbox.available_at <= datetime.now(UTC),
            )
            .order_by(NotificationOutbox.available_at, NotificationOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item is None:
            self._session.rollback()
            return None
        item.status = NotificationOutboxStatus.PROCESSING
        item.attempt_count += 1
        item.claimed_at = datetime.now(UTC)
        item.claim_token = uuid4()
        self._session.commit()
        return item

    def _deliver(self, item: NotificationOutbox) -> None:
        notification_type = NotificationType(item.notification_type)
        if not self._preference_enabled(item.recipient_user_id, notification_type):
            self._finish(item, NotificationOutboxStatus.SENT)
            return
        subscriptions = self._active_subscriptions(item.recipient_user_id)
        transient_errors = 0
        exhausted_errors = 0
        for subscription in subscriptions:
            delivery = self._session.get(NotificationDelivery, (item.id, subscription.id))
            if delivery is None:
                delivery = NotificationDelivery(
                    outbox_id=item.id,
                    subscription_id=subscription.id,
                    status=NotificationDeliveryStatus.PENDING,
                    attempt_count=0,
                    processed_at=None,
                    last_error=None,
                )
                self._session.add(delivery)
            elif delivery.status == NotificationDeliveryStatus.SENT:
                continue
            elif delivery.status == NotificationDeliveryStatus.FAILED:
                exhausted_errors += 1
                continue

            title, body = MESSAGES.get(subscription.locale, MESSAGES["en"])[notification_type]
            data = json.dumps(
                {
                    "title": title,
                    "body": body,
                    "url": str(item.payload.get("url", "/")),
                    "tag": item.deduplication_key,
                },
                ensure_ascii=False,
            )
            delivery.attempt_count += 1
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": {"p256dh": subscription.p256dh_key, "auth": subscription.auth_key},
                    },
                    data=data,
                    vapid_private_key=str(self._settings.push_vapid_private_key_file),
                    vapid_claims={"sub": self._settings.push_vapid_subject},
                    timeout=10,
                )
                subscription.last_success_at = datetime.now(UTC)
                subscription.failure_count = 0
                delivery.status = NotificationDeliveryStatus.SENT
                delivery.processed_at = datetime.now(UTC)
                delivery.last_error = None
            except WebPushException as error:
                status_code = error.response.status_code if error.response is not None else None
                logger.warning(
                    "Web Push delivery failed notification_id=%s status_code=%s error_type=%s",
                    item.id,
                    status_code,
                    type(error).__name__,
                )
                if status_code in {404, 410}:
                    self._session.delete(subscription)
                else:
                    if self._mark_delivery_failure(delivery, subscription):
                        exhausted_errors += 1
                    else:
                        transient_errors += 1
            except OSError as error:
                logger.warning(
                    "Web Push communication failed notification_id=%s error_type=%s",
                    item.id,
                    type(error).__name__,
                )
                if self._mark_delivery_failure(delivery, subscription):
                    exhausted_errors += 1
                else:
                    transient_errors += 1
        if transient_errors > 0:
            self._retry(item, "push_delivery_failed")
        elif exhausted_errors > 0:
            self._finish(item, NotificationOutboxStatus.FAILED, "push_delivery_failed")
        else:
            self._finish(item, NotificationOutboxStatus.SENT)

    @staticmethod
    def _mark_delivery_failure(delivery: NotificationDelivery, subscription: PushSubscription) -> bool:
        subscription.failure_count += 1
        delivery.last_error = "push_delivery_failed"
        if delivery.attempt_count >= 5:
            delivery.status = NotificationDeliveryStatus.FAILED
            delivery.processed_at = datetime.now(UTC)
            return True
        return False

    def _active_subscriptions(self, user_id) -> list[PushSubscription]:
        now = datetime.now(UTC)
        idle_cutoff = now - timedelta(seconds=self._settings.auth_session_idle_seconds)
        return list(
            self._session.scalars(
                select(PushSubscription)
                .join(UserSession, UserSession.id == PushSubscription.user_session_id)
                .join(User, User.id == PushSubscription.user_id)
                .where(
                    PushSubscription.user_id == user_id,
                    User.is_active.is_(True),
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                    UserSession.last_seen_at > idle_cutoff,
                    UserSession.created_at >= User.password_changed_at,
                )
            ).all()
        )

    def _preference_enabled(self, user_id, notification_type: NotificationType) -> bool:
        enabled = self._session.scalar(
            select(NotificationPreference.enabled).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
        )
        return DEFAULT_PREFERENCES[notification_type] if enabled is None else enabled

    def _recover_stale_claims(self) -> None:
        stale = list(
            self._session.scalars(
                select(NotificationOutbox)
                .where(
                    NotificationOutbox.status == NotificationOutboxStatus.PROCESSING,
                    NotificationOutbox.claimed_at < datetime.now(UTC) - timedelta(minutes=15),
                )
                .with_for_update(skip_locked=True)
            ).all()
        )
        for item in stale:
            item.status = NotificationOutboxStatus.PENDING
            item.available_at = datetime.now(UTC)
            item.claimed_at = None
            item.claim_token = None
        if stale:
            self._commit()

    def _finish(self, item: NotificationOutbox, status: NotificationOutboxStatus, error: str | None = None) -> None:
        claimed_item = self._lock_owned_claim(item)
        if claimed_item is None:
            return
        claimed_item.status = status
        claimed_item.processed_at = datetime.now(UTC)
        claimed_item.claimed_at = None
        claimed_item.claim_token = None
        claimed_item.last_error = error
        self._commit()

    def _retry(self, item: NotificationOutbox, error: str) -> None:
        claimed_item = self._lock_owned_claim(item)
        if claimed_item is None:
            return
        claimed_item.status = NotificationOutboxStatus.PENDING
        claimed_item.available_at = datetime.now(UTC) + timedelta(minutes=2**claimed_item.attempt_count)
        claimed_item.claimed_at = None
        claimed_item.claim_token = None
        claimed_item.last_error = error
        self._commit()

    def _lock_owned_claim(self, item: NotificationOutbox) -> NotificationOutbox | None:
        claimed_item = self._session.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.id == item.id,
                NotificationOutbox.status == NotificationOutboxStatus.PROCESSING,
                NotificationOutbox.claim_token == item.claim_token,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if claimed_item is None:
            self._session.rollback()
        return claimed_item

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise
