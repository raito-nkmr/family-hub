from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import require_csrf_token
from app.features.auth.public import AuthContext
from app.features.notifications.models import NotificationType
from app.features.notifications.router import (
    delete_push_subscription,
    router,
    update_notification_preferences,
    update_push_subscription_locale,
)
from app.features.notifications.schemas import (
    NotificationPreferenceItem,
    NotificationPreferenceUpdate,
    PushSubscriptionLocaleUpdate,
)
from app.features.notifications.service import NotificationPersistenceError, NotificationService
from app.main import create_app
from tests.features.auth.factories import make_user_session


def make_context() -> AuthContext:
    user_session = make_user_session()
    return AuthContext(user=user_session.user, user_session=user_session)


def make_preferences() -> NotificationPreferenceUpdate:
    return NotificationPreferenceUpdate(
        items=[
            NotificationPreferenceItem(notification_type=notification_type, enabled=True)
            for notification_type in NotificationType
        ]
    )


def test_unsubscribe_persistence_failure_returns_service_unavailable() -> None:
    service = MagicMock(spec=NotificationService)
    service.unsubscribe.side_effect = NotificationPersistenceError

    with pytest.raises(HTTPException) as error:
        delete_push_subscription(uuid4(), make_context(), service)

    assert error.value.status_code == 503


def test_preference_persistence_failure_returns_service_unavailable() -> None:
    service = MagicMock(spec=NotificationService)
    service.update_preferences.side_effect = NotificationPersistenceError

    with pytest.raises(HTTPException) as error:
        update_notification_preferences(make_preferences(), make_context(), service)

    assert error.value.status_code == 503


def test_locale_persistence_failure_returns_service_unavailable() -> None:
    service = MagicMock(spec=NotificationService)
    service.update_subscription_locale.side_effect = NotificationPersistenceError

    with pytest.raises(HTTPException) as error:
        update_push_subscription_locale(PushSubscriptionLocaleUpdate(locale="ja"), make_context(), service)

    assert error.value.status_code == 503


def test_notification_routes_are_registered_and_mutations_require_csrf() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "get" in paths["/api/v1/notifications/config"]
    assert {"post"} <= set(paths["/api/v1/notifications/subscriptions"])
    assert {"delete"} <= set(paths["/api/v1/notifications/subscriptions/{subscription_id}"])
    assert {"put"} <= set(paths["/api/v1/notifications/subscriptions/locale"])
    assert {"put"} <= set(paths["/api/v1/notifications/preferences"])
    mutation_routes = [route for route in router.routes if route.methods & {"POST", "PUT", "DELETE"}]
    assert mutation_routes
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies)
        for route in mutation_routes
    )
