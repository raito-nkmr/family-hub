import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import Settings
from app.features.auth.dependencies import (
    get_auth_context,
    get_auth_service,
    get_cookie_name,
    get_login_rate_limiter,
    require_csrf_token,
    require_trusted_origin,
)
from app.features.auth.rate_limit import LoginRateLimiter
from app.features.auth.schemas import (
    AuthSessionResponse,
    LoginRequest,
    PasswordChangeRequest,
    UserResponse,
    UserSessionListResponse,
    UserSessionResponse,
)
from app.features.auth.service import (
    AuthContext,
    AuthService,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    UserSessionNotFoundError,
)

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


def _session_response(context: AuthContext) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=UserResponse(
            id=context.user.id,
            username=context.user.username,
            system_role=context.user.system_role,
        ),
        csrf_token=context.user_session.csrf_token,
    )


def _delete_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        get_cookie_name(settings),
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[LoginRateLimiter, Depends(get_login_rate_limiter)],
) -> AuthSessionResponse:
    client_host = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_host}:{credentials.username}"
    retry_after = rate_limiter.retry_after(rate_limit_key)
    if retry_after is not None:
        logger.warning("Login rate limit triggered username=%s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        created = service.login(credentials.username, credentials.password)
    except InvalidCredentialsError as error:
        rate_limiter.record_failure(rate_limit_key)
        logger.warning("Login failed username=%s", credentials.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password") from error

    rate_limiter.reset(rate_limit_key)
    logger.info("Login succeeded user_id=%s", created.user.id)
    settings: Settings = request.app.state.settings
    response.set_cookie(
        key=get_cookie_name(settings),
        value=created.token,
        max_age=settings.auth_session_absolute_seconds,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return AuthSessionResponse(
        user=UserResponse(
            id=created.user.id,
            username=created.user.username,
            system_role=created.user.system_role,
        ),
        csrf_token=created.csrf_token,
    )


@router.get("/me", response_model=AuthSessionResponse)
def get_current_session(context: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthSessionResponse:
    return _session_response(context)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_token)])
def logout(
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    service.logout(context)
    _delete_session_cookie(response, request.app.state.settings)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf_token)])
def logout_all(
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    service.logout_all(context.user.id)
    _delete_session_cookie(response, request.app.state.settings)


@router.get("/sessions", response_model=UserSessionListResponse)
def list_sessions(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserSessionListResponse:
    return UserSessionListResponse(
        items=[
            UserSessionResponse(
                id=user_session.id,
                created_at=user_session.created_at,
                last_seen_at=user_session.last_seen_at,
                expires_at=user_session.expires_at,
                current=user_session.id == context.user_session.id,
            )
            for user_session in service.list_sessions(context)
        ]
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def revoke_session(
    session_id: UUID,
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    try:
        revoked_current = service.revoke_session(context, session_id)
    except UserSessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found") from error
    if revoked_current:
        _delete_session_cookie(response, request.app.state.settings)


@router.put(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    try:
        service.change_password(context, body.current_password, body.new_password)
    except InvalidCurrentPasswordError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect") from error
    _delete_session_cookie(response, request.app.state.settings)
