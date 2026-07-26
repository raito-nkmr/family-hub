from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request, Response

from app.core.config import Settings
from app.features.auth.dependencies import get_auth_context, require_trusted_origin
from app.features.auth.rate_limit import LoginRateLimiter
from app.features.auth.router import change_password, get_current_session, list_sessions, login, logout, revoke_session
from app.features.auth.schemas import LoginRequest, PasswordChangeRequest
from app.features.auth.service import (
    AuthContext,
    AuthService,
    CreatedSession,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
)
from app.main import create_app
from tests.features.auth.factories import make_user, make_user_session


def make_request(*, origin: str = "http://localhost:5173", cookie: str | None = None) -> Request:
    headers = [(b"origin", origin.encode("ascii"))]
    if cookie is not None:
        headers.append((b"cookie", f"photo_session={cookie}".encode("ascii")))
    settings = Settings(app_env="test")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
    }
    return Request(scope)


class AuthServiceStub:
    def __init__(self, *, invalid_credentials: bool = False) -> None:
        self.user = make_user()
        self.user_session = make_user_session(self.user)
        self.invalid_credentials = invalid_credentials
        self.logged_out = False

    def login(self, username: str, password: str) -> CreatedSession:
        if self.invalid_credentials:
            raise InvalidCredentialsError
        return CreatedSession(user=self.user, token="session-token", csrf_token=self.user_session.csrf_token)

    def authenticate(self, token: str) -> AuthContext | None:
        if token != "session-token":
            return None
        return AuthContext(user=self.user, user_session=self.user_session)

    def logout(self, context: AuthContext) -> None:
        self.logged_out = True


def test_login_sets_http_only_session_cookie() -> None:
    request = make_request()
    response = Response()
    service = AuthServiceStub()

    result = login(
        LoginRequest(username="owner", password="password"),
        request,
        response,
        service,
        LoginRateLimiter(maximum_attempts=5, window_seconds=300),
    )

    assert result.user.username == "owner"
    assert result.user.system_role.value == "user"
    assert result.csrf_token == service.user_session.csrf_token
    cookie = response.headers["set-cookie"]
    assert "photo_session=session-token" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_login_returns_generic_unauthorized_error() -> None:
    with pytest.raises(HTTPException) as error:
        login(
            LoginRequest(username="owner", password="wrong"),
            make_request(),
            Response(),
            AuthServiceStub(invalid_credentials=True),
            LoginRateLimiter(maximum_attempts=5, window_seconds=300),
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid username or password"


def test_current_session_returns_user_and_csrf_token() -> None:
    service = AuthServiceStub()
    context = AuthContext(user=service.user, user_session=service.user_session)

    result = get_current_session(context)

    assert result.user.username == "owner"
    assert result.csrf_token == service.user_session.csrf_token


def test_logout_revokes_session_and_deletes_cookie() -> None:
    request = make_request(cookie="session-token")
    response = Response()
    service = AuthServiceStub()
    context = AuthContext(user=service.user, user_session=service.user_session)

    logout(request, response, context, service)

    assert service.logged_out is True
    assert "photo_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_auth_context_requires_valid_cookie() -> None:
    service = AuthServiceStub()

    with pytest.raises(HTTPException) as error:
        get_auth_context(make_request(), service)

    assert error.value.status_code == 401


def test_auth_context_accepts_valid_cookie() -> None:
    service = AuthServiceStub()

    context = get_auth_context(make_request(cookie="session-token"), service)

    assert context.user is service.user


def test_login_requires_configured_origin() -> None:
    with pytest.raises(HTTPException) as error:
        require_trusted_origin(make_request(origin="https://attacker.example"))

    assert error.value.status_code == 403


def test_list_sessions_marks_current_session() -> None:
    user = make_user()
    current = make_user_session(user)
    another = make_user_session(user)
    context = AuthContext(user=user, user_session=current)
    service = MagicMock(spec=AuthService)
    service.list_sessions.return_value = [current, another]

    result = list_sessions(context, service)

    assert [item.current for item in result.items] == [True, False]


def test_revoke_current_session_deletes_cookie() -> None:
    user = make_user()
    current = make_user_session(user)
    context = AuthContext(user=user, user_session=current)
    service = MagicMock(spec=AuthService)
    service.revoke_session.return_value = True
    response = Response()

    revoke_session(current.id, make_request(), response, context, service)

    assert "Max-Age=0" in response.headers["set-cookie"]


def test_change_password_deletes_cookie() -> None:
    user = make_user()
    context = AuthContext(user=user, user_session=make_user_session(user))
    service = MagicMock(spec=AuthService)
    response = Response()

    change_password(
        PasswordChangeRequest(current_password="password", new_password="new-password"),
        make_request(),
        response,
        context,
        service,
    )

    service.change_password.assert_called_once_with(context, "password", "new-password")
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_change_password_rejects_incorrect_current_password() -> None:
    user = make_user()
    context = AuthContext(user=user, user_session=make_user_session(user))
    service = MagicMock(spec=AuthService)
    service.change_password.side_effect = InvalidCurrentPasswordError

    with pytest.raises(HTTPException) as error:
        change_password(
            PasswordChangeRequest(current_password="wrong", new_password="new-password"),
            make_request(),
            Response(),
            context,
            service,
        )

    assert error.value.status_code == 400


def test_account_security_routes_are_in_openapi_schema() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "get" in paths["/api/v1/auth/sessions"]
    assert "delete" in paths["/api/v1/auth/sessions/{session_id}"]
    assert "put" in paths["/api/v1/auth/password"]
