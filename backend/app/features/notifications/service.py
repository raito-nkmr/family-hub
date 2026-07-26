import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.public import AuthContext, User
from app.features.notifications.models import NotificationPreference, NotificationType, PushSubscription
from app.features.notifications.schemas import NotificationPreferenceItem, PushSubscriptionCreate

DEFAULT_PREFERENCES = {
    NotificationType.PHOTO_SHARED: True,
    NotificationType.CLEANING_DUE: True,
    NotificationType.SHOPPING_ADDED: False,
}


class NotificationPersistenceError(Exception):
    pass


class NotificationEndpointNotAllowedError(Exception):
    pass


class NotificationSubscriptionLimitError(Exception):
    pass


class NotificationService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self._settings.push_vapid_public_key
            and self._settings.push_vapid_private_key_file
            and self._settings.push_vapid_subject
        )

    def config(self, context: AuthContext) -> dict[str, object]:
        subscriptions = list(
            self._session.scalars(
                select(PushSubscription).where(
                    PushSubscription.user_id == context.user.id,
                    PushSubscription.user_session_id == context.user_session.id,
                )
            ).all()
        )
        return {
            "enabled": self.enabled,
            "vapid_public_key": self._settings.push_vapid_public_key if self.enabled else None,
            "subscription_ids": [subscription.id for subscription in subscriptions],
            "preferences": self.preferences(context.user.id),
        }

    def subscribe(self, context: AuthContext, body: PushSubscriptionCreate) -> PushSubscription:
        if not self.enabled:
            raise NotificationPersistenceError("Web Push is not configured")
        endpoint = str(body.endpoint)
        endpoint_host = body.endpoint.host.lower() if body.endpoint.host else ""
        if endpoint_host not in self._settings.push_allowed_endpoint_host_list:
            raise NotificationEndpointNotAllowedError
        self._session.scalar(select(User.id).where(User.id == context.user.id).with_for_update())
        endpoint_hash = hashlib.sha256(endpoint.encode()).hexdigest()
        subscription = self._session.scalar(
            select(PushSubscription).where(PushSubscription.endpoint_hash == endpoint_hash).with_for_update()
        )
        if subscription is None or subscription.user_id != context.user.id:
            subscription_count = self._session.scalar(
                select(func.count(PushSubscription.id)).where(PushSubscription.user_id == context.user.id)
            )
            if (subscription_count or 0) >= self._settings.push_max_subscriptions_per_user:
                raise NotificationSubscriptionLimitError
        if subscription is None:
            subscription = PushSubscription(
                id=uuid4(),
                user_id=context.user.id,
                user_session_id=context.user_session.id,
                endpoint_hash=endpoint_hash,
                endpoint=endpoint,
                p256dh_key=body.keys.p256dh,
                auth_key=body.keys.auth,
                locale=body.locale,
                created_at=datetime.now(UTC),
                last_success_at=None,
                failure_count=0,
            )
            self._session.add(subscription)
        else:
            subscription.user_id = context.user.id
            subscription.user_session_id = context.user_session.id
            subscription.endpoint = endpoint
            subscription.p256dh_key = body.keys.p256dh
            subscription.auth_key = body.keys.auth
            subscription.locale = body.locale
            subscription.failure_count = 0
        self._commit()
        return subscription

    def unsubscribe(self, context: AuthContext, subscription_id: UUID) -> None:
        self._session.execute(
            delete(PushSubscription).where(
                PushSubscription.id == subscription_id,
                PushSubscription.user_id == context.user.id,
                PushSubscription.user_session_id == context.user_session.id,
            )
        )
        self._commit()

    def preferences(self, user_id: UUID) -> list[NotificationPreferenceItem]:
        records = {
            NotificationType(record.notification_type): record.enabled
            for record in self._session.scalars(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            ).all()
        }
        return [
            NotificationPreferenceItem(
                notification_type=notification_type,
                enabled=records.get(notification_type, default),
            )
            for notification_type, default in DEFAULT_PREFERENCES.items()
        ]

    def update_preferences(
        self,
        user_id: UUID,
        items: list[NotificationPreferenceItem],
    ) -> list[NotificationPreferenceItem]:
        if {item.notification_type for item in items} != set(NotificationType):
            raise ValueError("Every notification preference must be provided exactly once")
        now = datetime.now(UTC)
        for item in items:
            statement = insert(NotificationPreference).values(
                user_id=user_id,
                notification_type=item.notification_type,
                enabled=item.enabled,
                updated_at=now,
            )
            self._session.execute(
                statement.on_conflict_do_update(
                    index_elements=[NotificationPreference.user_id, NotificationPreference.notification_type],
                    set_={"enabled": statement.excluded.enabled, "updated_at": statement.excluded.updated_at},
                )
            )
        self._commit()
        return self.preferences(user_id)

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise NotificationPersistenceError from error
