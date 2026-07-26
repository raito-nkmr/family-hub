import pytest
from pydantic import ValidationError

from app.features.auth.schemas import InvitationAccept, InvitationCreate, LoginRequest, normalize_username


def test_login_request_normalizes_username() -> None:
    request = LoginRequest(username=" Owner ", password="password")

    assert request.username == "owner"


@pytest.mark.parametrize("username", ["owner@example.com", "owner name", "家族👪"])
def test_username_rejects_unsupported_values(username: str) -> None:
    with pytest.raises(ValueError):
        normalize_username(username)


def test_username_accepts_and_normalizes_japanese_characters() -> None:
    assert normalize_username("  タロウ１２  ") == "タロウ12"


def test_login_request_limits_password_length() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(username="owner", password="x" * 129)


def test_invitation_create_normalizes_username() -> None:
    request = InvitationCreate(username=" Family-Member ")

    assert request.username == "family-member"


def test_invitation_accept_requires_long_password() -> None:
    with pytest.raises(ValidationError):
        InvitationAccept(token="t" * 43, password="short-7")


def test_invitation_accept_allows_eight_character_password() -> None:
    request = InvitationAccept(token="t" * 43, password="eight888")

    assert request.password == "eight888"
