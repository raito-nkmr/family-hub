from dataclasses import dataclass
from hmac import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_session
from app.features.auth.models import SystemRole
from app.features.auth.rate_limit import LoginRateLimiter
from app.features.auth.service import AuthContext, AuthService


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: UUID
    username: str
    system_role: SystemRole = SystemRole.USER


def get_auth_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> AuthService:
    return AuthService(session, request.app.state.settings)


def get_login_rate_limiter(request: Request) -> LoginRateLimiter:
    return request.app.state.login_rate_limiter


def get_cookie_name(settings: Settings) -> str:
    return "__Host-photo_session" if settings.auth_cookie_secure else "photo_session"


def get_auth_context(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthContext:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(get_cookie_name(settings))
    context = service.authenticate(token) if token else None
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return context


def require_authenticated_user(context: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=context.user.id,
        username=context.user.username,
        system_role=SystemRole(context.user.system_role),
    )


def require_system_admin(user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)]) -> AuthenticatedUser:
    if user.system_role is not SystemRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System administrator required")
    return user


def require_csrf_token(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if csrf_token is None or not compare_digest(csrf_token, context.user_session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def require_trusted_origin(request: Request) -> None:
    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin", "").rstrip("/")
    if not origin or origin not in settings.auth_trusted_origin_list:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted request origin")
