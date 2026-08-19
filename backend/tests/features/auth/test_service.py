from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.service import (
    AuthContext,
    AuthService,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    UserSessionNotFoundError,
    hash_session_token,
)
from tests.features.auth.factories import make_user, make_user_session


def make_service(session: Session) -> AuthService:
    return AuthService(session, Settings(app_env="test"))


def test_login_creates_hashed_server_side_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    session.scalar.return_value = user
    monkeypatch.setattr("app.features.auth.service.verify_password", lambda password, password_hash: True)

    result = make_service(session).login("owner", "password")

    created_session = session.add.call_args.args[0]
    assert result.user is user
    assert created_session.token_hash == hash_session_token(result.token)
    assert created_session.csrf_token == result.csrf_token
    assert result.token not in created_session.token_hash
    session.commit.assert_called_once_with()


def test_login_uses_dummy_hash_for_unknown_user(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    verify_dummy = MagicMock()
    monkeypatch.setattr("app.features.auth.service.verify_dummy_password", verify_dummy)

    with pytest.raises(InvalidCredentialsError):
        make_service(session).login("missing", "password")

    verify_dummy.assert_called_once_with("password")
    session.add.assert_not_called()


def test_login_verifies_password_before_rejecting_disabled_user(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    user.is_active = False
    session.scalar.return_value = user
    verify = MagicMock(return_value=True)
    monkeypatch.setattr("app.features.auth.service.verify_password", verify)

    with pytest.raises(InvalidCredentialsError):
        make_service(session).login("owner", "password")

    verify.assert_called_once_with("password", user.password_hash)


def test_authenticate_returns_active_session() -> None:
    session = MagicMock(spec=Session)
    user_session = make_user_session()
    session.scalar.return_value = user_session

    context = make_service(session).authenticate("session-token")

    assert context is not None
    assert context.user is user_session.user
    assert context.user_session is user_session
    session.commit.assert_not_called()


def test_authenticate_rejects_expired_session() -> None:
    session = MagicMock(spec=Session)
    user_session = make_user_session()
    user_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.scalar.return_value = user_session

    assert make_service(session).authenticate("session-token") is None


def test_logout_revokes_session() -> None:
    session = MagicMock(spec=Session)
    user_session = make_user_session()
    session.scalar.return_value = user_session
    context = make_service(session).authenticate("session-token")
    assert context is not None

    make_service(session).logout(context)

    assert user_session.revoked_at is not None
    session.commit.assert_called_once_with()


def test_list_sessions_returns_active_sessions() -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    current = make_user_session(user)
    another = make_user_session(user)
    session.scalars.return_value.all.return_value = [current, another]
    context = AuthContext(user=user, user_session=current)

    result = make_service(session).list_sessions(context)

    assert result == [current, another]
    session.scalars.assert_called_once()


def test_revoke_session_only_revokes_owned_active_session() -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    current = make_user_session(user)
    another = make_user_session(user)
    session.scalar.return_value = another
    context = AuthContext(user=user, user_session=current)

    revoked_current = make_service(session).revoke_session(context, another.id)

    assert revoked_current is False
    assert another.revoked_at is not None
    session.commit.assert_called_once_with()


def test_revoke_session_rejects_unknown_session() -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    context = AuthContext(user=user, user_session=make_user_session(user))
    session.scalar.return_value = None

    with pytest.raises(UserSessionNotFoundError):
        make_service(session).revoke_session(context, context.user_session.id)


def test_change_password_rehashes_password_and_revokes_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    session.scalar.return_value = user
    context = AuthContext(user=user, user_session=make_user_session(user))
    monkeypatch.setattr("app.features.auth.service.verify_password", lambda password, password_hash: True)
    monkeypatch.setattr("app.features.auth.service.hash_password", lambda password: "new-password-hash")

    make_service(session).change_password(context, "current password", "new password")

    assert user.password_hash == "new-password-hash"
    assert user.password_changed_at >= context.user_session.created_at
    assert user.must_change_password is False
    session.execute.assert_called_once()
    session.commit.assert_called_once_with()


def test_change_password_rejects_incorrect_current_password(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    user = make_user()
    session.scalar.return_value = user
    context = AuthContext(user=user, user_session=make_user_session(user))
    monkeypatch.setattr("app.features.auth.service.verify_password", lambda password, password_hash: False)

    with pytest.raises(InvalidCurrentPasswordError):
        make_service(session).change_password(context, "wrong password", "new password")

    session.execute.assert_not_called()
    session.commit.assert_not_called()
