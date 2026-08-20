import pytest
from pydantic import ValidationError

from app.features.notifications.schemas import PushSubscriptionCreate, PushSubscriptionLocaleUpdate


def make_subscription(endpoint: str) -> PushSubscriptionCreate:
    return PushSubscriptionCreate(
        endpoint=endpoint,
        keys={"p256dh": "p" * 20, "auth": "a" * 10},
        locale="en",
    )


def test_push_endpoint_requires_https() -> None:
    with pytest.raises(ValidationError, match="must use HTTPS"):
        make_subscription("http://web.push.apple.com/subscription")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user@web.push.apple.com/subscription",
        "https://web.push.apple.com:8443/subscription",
        "https://web.push.apple.com/subscription#fragment",
    ],
)
def test_push_endpoint_rejects_unsupported_url_components(endpoint: str) -> None:
    with pytest.raises(ValidationError, match="unsupported URL components"):
        make_subscription(endpoint)


@pytest.mark.parametrize("locale", ["en", "ja"])
def test_push_subscription_locale_update_accepts_supported_locale(locale: str) -> None:
    assert PushSubscriptionLocaleUpdate(locale=locale).locale == locale


def test_push_subscription_locale_update_rejects_unknown_locale() -> None:
    with pytest.raises(ValidationError):
        PushSubscriptionLocaleUpdate(locale="fr")
