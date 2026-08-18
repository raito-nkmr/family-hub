import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import (
    AuthenticatedUser,
    get_cookie_name,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
    require_system_admin,
)
from app.features.auth.models import SystemRole
from app.features.auth.service import AuthContext
from tests.features.auth.factories import make_user_session


def test_cookie_name_uses_host_prefix_for_secure_cookie() -> None:
    assert get_cookie_name(Settings(auth_cookie_secure=False)) == "photo_session"
    assert get_cookie_name(Settings(auth_cookie_secure=True)) == "__Host-photo_session"


def test_csrf_dependency_accepts_matching_session_token() -> None:
    user_session = make_user_session()
    context = AuthContext(user=user_session.user, user_session=user_session)

    require_csrf_token(context, user_session.csrf_token)


def test_authenticated_user_dependency_returns_public_identity() -> None:
    user_session = make_user_session()
    context = AuthContext(user=user_session.user, user_session=user_session)

    user = require_authenticated_user(context)

    assert user.id == user_session.user.id
    assert user.username == user_session.user.username
    assert user.system_role is SystemRole.USER


def test_system_admin_dependency_rejects_regular_user() -> None:
    with pytest.raises(HTTPException) as error:
        require_system_admin(AuthenticatedUser(id=make_user_session().user.id, username="owner"))

    assert error.value.status_code == 403


def test_system_admin_dependency_accepts_administrator() -> None:
    user = AuthenticatedUser(
        id=make_user_session().user.id,
        username="owner",
        system_role=SystemRole.ADMIN,
    )

    assert require_system_admin(user) is user


def test_csrf_dependency_rejects_invalid_token() -> None:
    user_session = make_user_session()
    context = AuthContext(user=user_session.user, user_session=user_session)

    with pytest.raises(HTTPException) as error:
        require_csrf_token(context, "wrong-token")

    assert error.value.status_code == 403


def test_password_change_dependency_accepts_regular_user() -> None:
    user = AuthenticatedUser(id=make_user_session().user.id, username="owner")

    require_password_change_complete(user)


def test_password_change_dependency_rejects_temporary_password() -> None:
    user = AuthenticatedUser(id=make_user_session().user.id, username="owner", must_change_password=True)

    with pytest.raises(HTTPException) as error:
        require_password_change_complete(user)

    assert error.value.status_code == 403
