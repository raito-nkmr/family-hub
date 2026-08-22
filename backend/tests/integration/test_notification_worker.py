import os
from datetime import UTC, datetime, timedelta
from importlib import import_module
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import create_database_engine
from app.features.auth.models import SystemRole, User, UserSession
from app.features.notifications.models import (
    NotificationDelivery,
    NotificationDeliveryStatus,
    NotificationOutbox,
    NotificationOutboxStatus,
    NotificationType,
    PushSubscription,
)

pywebpush = pytest.importorskip("pywebpush")
WebPushException = pywebpush.WebPushException
NotificationWorker = import_module("app.features.notifications.worker").NotificationWorker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def add_notification_records(session: Session, *, subscription_count: int = 0) -> tuple[User, NotificationOutbox]:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        username=f"notification-{uuid4().hex}",
        password_hash="password-hash",
        is_active=True,
        system_role=SystemRole.USER,
        created_at=now - timedelta(days=1),
        password_changed_at=now - timedelta(hours=2),
    )
    user_session = UserSession(
        id=uuid4(),
        user_id=user.id,
        token_hash=uuid4().hex * 2,
        csrf_token="c" * 43,
        created_at=now - timedelta(hours=1),
        last_used_at=now,
        expires_at=now + timedelta(days=1),
        revoked_at=None,
    )
    item = NotificationOutbox(
        id=uuid4(),
        recipient_user_id=user.id,
        notification_type=NotificationType.PHOTO_SHARED,
        deduplication_key=f"test:{uuid4()}",
        payload={"url": "/photos/new"},
        status=NotificationOutboxStatus.PENDING,
        attempt_count=0,
        available_at=now - timedelta(hours=1),
        created_at=now - timedelta(hours=1),
        processed_at=None,
        claimed_at=None,
        claim_token=None,
        last_error=None,
    )
    session.add(user)
    session.flush()
    session.add(user_session)
    session.flush()
    session.add(item)
    for index in range(subscription_count):
        endpoint = f"https://web.push.apple.com/{'ok' if index == 0 else 'retry'}"
        session.add(
            PushSubscription(
                id=uuid4(),
                user_id=user.id,
                user_session_id=user_session.id,
                endpoint_hash=f"{index:064d}",
                endpoint=endpoint,
                p256dh_key="p" * 20,
                auth_key="a" * 10,
                locale="en",
                created_at=now,
                last_success_at=None,
                failure_count=0,
            )
        )
    session.commit()
    return user, item


def worker_settings() -> Settings:
    assert TEST_DATABASE_URL is not None
    return Settings(
        app_env="test",
        database_url=TEST_DATABASE_URL,
        push_vapid_public_key="public",
        push_vapid_private_key_file="/tmp/private-key",
        push_vapid_subject="mailto:admin@example.com",
    )


def test_recent_claim_is_not_recovered_from_an_old_available_time() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_database_engine(worker_settings())
    with Session(engine, expire_on_commit=False) as first_session:
        user, item = add_notification_records(first_session)
        claimed = NotificationWorker(first_session, worker_settings())._claim_one()
        assert claimed is not None

        with Session(engine) as second_session:
            NotificationWorker(second_session, worker_settings())._recover_stale_claims()

        first_session.refresh(item)
        assert item.status == NotificationOutboxStatus.PROCESSING
        assert item.claimed_at is not None
        assert item.claim_token is not None
        first_session.execute(delete(User).where(User.id == user.id))
        first_session.commit()
    engine.dispose()


def test_retry_sends_only_to_subscriptions_that_have_not_succeeded(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_database_engine(worker_settings())
    calls: list[str] = []
    retry_should_fail = True

    def send_push(**kwargs: object) -> None:
        nonlocal retry_should_fail
        subscription_info = kwargs["subscription_info"]
        assert isinstance(subscription_info, dict)
        endpoint = str(subscription_info["endpoint"])
        calls.append(endpoint)
        if endpoint.endswith("/retry") and retry_should_fail:
            raise WebPushException("temporary failure")

    monkeypatch.setattr("app.features.notifications.worker.webpush", send_push)

    with Session(engine, expire_on_commit=False) as session:
        user, item = add_notification_records(session, subscription_count=2)
        worker = NotificationWorker(session, worker_settings())

        assert worker.process(limit=1) == 1
        session.refresh(item)
        deliveries = list(
            session.scalars(select(NotificationDelivery).where(NotificationDelivery.outbox_id == item.id))
        )
        statuses = {delivery.status for delivery in deliveries}
        assert statuses == {NotificationDeliveryStatus.SENT, NotificationDeliveryStatus.PENDING}
        assert item.status == NotificationOutboxStatus.PENDING

        calls.clear()
        retry_should_fail = False
        item.available_at = datetime.now(UTC)
        session.commit()

        assert worker.process(limit=1) == 1
        session.refresh(item)
        assert calls == ["https://web.push.apple.com/retry"]
        assert item.status == NotificationOutboxStatus.SENT

        session.execute(delete(User).where(User.id == user.id))
        session.commit()
    engine.dispose()


def test_communication_exception_requeues_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_database_engine(worker_settings())

    def send_push(**kwargs: object) -> None:
        raise TimeoutError("push service timed out")

    monkeypatch.setattr("app.features.notifications.worker.webpush", send_push)

    with Session(engine, expire_on_commit=False) as session:
        user, item = add_notification_records(session, subscription_count=1)
        worker = NotificationWorker(session, worker_settings())

        assert worker.process(limit=1) == 1
        session.refresh(item)
        delivery = session.scalar(select(NotificationDelivery).where(NotificationDelivery.outbox_id == item.id))
        assert delivery is not None
        assert item.status == NotificationOutboxStatus.PENDING
        assert delivery.status == NotificationDeliveryStatus.PENDING
        assert delivery.last_error == "push_delivery_failed"

        session.execute(delete(User).where(User.id == user.id))
        session.commit()
    engine.dispose()
