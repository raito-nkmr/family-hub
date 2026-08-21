from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.public import AuthContext
from app.features.notifications.schemas import PushSubscriptionCreate, PushSubscriptionLocaleUpdate
from app.features.notifications.service import (
    NotificationEndpointNotAllowedError,
    NotificationService,
    NotificationSubscriptionEndpointConflictError,
    NotificationSubscriptionLimitError,
)
from tests.features.auth.factories import make_user_session


def make_context() -> AuthContext:
    user_session = make_user_session()
    return AuthContext(user=user_session.user, user_session=user_session)


def make_body(endpoint: str = "https://web.push.apple.com/subscription") -> PushSubscriptionCreate:
    return PushSubscriptionCreate(
        endpoint=endpoint,
        keys={"p256dh": "p" * 20, "auth": "a" * 10},
    )


def make_service(session: MagicMock, **settings: object) -> NotificationService:
    return NotificationService(
        session,
        Settings(
            app_env="test",
            push_vapid_public_key="public",
            push_vapid_private_key_file="/tmp/private-key",
            push_vapid_subject="mailto:admin@example.com",
            **settings,
        ),
    )


def test_subscribe_rejects_endpoint_host_outside_allowlist() -> None:
    session = MagicMock(spec=Session)
    service = make_service(session)

    with pytest.raises(NotificationEndpointNotAllowedError):
        service.subscribe(make_context(), make_body("https://example.com/push"))

    session.scalar.assert_not_called()


def test_subscribe_enforces_per_user_limit() -> None:
    session = MagicMock(spec=Session)
    context = make_context()
    session.scalar.side_effect = [context.user.id, None, 1]
    service = make_service(session, push_max_subscriptions_per_user=1)

    with pytest.raises(NotificationSubscriptionLimitError):
        service.subscribe(context, make_body())

    session.add.assert_not_called()


def test_subscribe_rejects_an_endpoint_owned_by_another_user() -> None:
    session = MagicMock(spec=Session)
    context = make_context()
    existing_subscription = MagicMock()
    existing_subscription.user_id = uuid4()
    existing_subscription.user_session_id = uuid4()
    existing_subscription.endpoint = "https://web.push.apple.com/owned-by-another-user"
    session.scalar.side_effect = [context.user.id, existing_subscription]
    service = make_service(session)

    with pytest.raises(NotificationSubscriptionEndpointConflictError):
        service.subscribe(context, make_body())

    session.add.assert_not_called()
    session.commit.assert_not_called()
    assert existing_subscription.user_id != context.user.id
    assert existing_subscription.endpoint == "https://web.push.apple.com/owned-by-another-user"


def test_update_subscription_locale_updates_current_session_subscriptions() -> None:
    session = MagicMock(spec=Session)
    context = make_context()
    service = make_service(session)

    service.update_subscription_locale(context, PushSubscriptionLocaleUpdate(locale="ja"))

    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "UPDATE push_subscriptions SET locale='ja'" in sql
    assert "push_subscriptions.user_id" in sql
    assert "push_subscriptions.user_session_id" in sql
    session.commit.assert_called_once_with()
