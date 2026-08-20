from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.features.auth.admin_dependencies import get_administrative_service
from app.features.auth.admin_service import (
    AdministrativeGroupMemberError,
    AdministrativePersistenceError,
    AdministrativeReauthenticationError,
    AdministrativeService,
    AdministrativeUserNotFoundError,
    LastSystemAdministratorError,
    UserOwnsGroupsWithoutAnotherAdminError,
)
from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_csrf_token,
    require_password_change_complete,
    require_system_admin,
)
from app.features.auth.schemas import (
    AdministrativeAuditEventListResponse,
    AdministrativeAuditEventResponse,
    AdministrativeGroupAdministratorAssignment,
    AdministrativeGroupHealthListResponse,
    AdministrativeGroupHealthResponse,
    AdministrativeUserListResponse,
    AdministrativeUserResponse,
    AdministrativeUserRoleUpdate,
    AdministrativeUserStatusUpdate,
)

router = APIRouter(
    tags=["admin users"],
    dependencies=[Depends(require_system_admin), Depends(require_password_change_complete)],
)

_ADMINISTRATIVE_ERRORS = (
    AdministrativeUserNotFoundError,
    AdministrativeReauthenticationError,
    LastSystemAdministratorError,
    UserOwnsGroupsWithoutAnotherAdminError,
    AdministrativePersistenceError,
    AdministrativeGroupMemberError,
)


def _raise_admin_error(error: Exception) -> None:
    if isinstance(error, AdministrativeUserNotFoundError):
        raise HTTPException(status_code=404, detail="User not found") from error
    if isinstance(error, AdministrativeReauthenticationError):
        raise HTTPException(status_code=403, detail="Current password is incorrect") from error
    if isinstance(error, LastSystemAdministratorError):
        raise HTTPException(status_code=409, detail="At least one active system administrator is required") from error
    if isinstance(error, UserOwnsGroupsWithoutAnotherAdminError):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "User is the last active administrator of one or more groups",
                "groups": error.group_names,
            },
        ) from error
    if isinstance(error, AdministrativePersistenceError):
        raise HTTPException(status_code=500, detail="Could not update user") from error
    if isinstance(error, AdministrativeGroupMemberError):
        raise HTTPException(status_code=404, detail="Active group member not found") from error
    raise error


@router.get("/users", response_model=AdministrativeUserListResponse)
def list_users(
    service: Annotated[AdministrativeService, Depends(get_administrative_service)],
) -> AdministrativeUserListResponse:
    return AdministrativeUserListResponse(
        items=[AdministrativeUserResponse.model_validate(item, from_attributes=True) for item in service.list_users()]
    )


@router.patch(
    "/users/{user_id}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def update_user_status(
    user_id: UUID,
    body: AdministrativeUserStatusUpdate,
    administrator: Annotated[AuthenticatedUser, Depends(require_system_admin)],
    service: Annotated[AdministrativeService, Depends(get_administrative_service)],
) -> None:
    try:
        service.update_user_status(
            user_id,
            body.is_active,
            administrator.id,
            administrator.username,
            body.current_password,
        )
    except _ADMINISTRATIVE_ERRORS as error:
        _raise_admin_error(error)


@router.patch(
    "/users/{user_id}/role",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def update_user_role(
    user_id: UUID,
    body: AdministrativeUserRoleUpdate,
    administrator: Annotated[AuthenticatedUser, Depends(require_system_admin)],
    service: Annotated[AdministrativeService, Depends(get_administrative_service)],
) -> None:
    try:
        service.update_user_role(
            user_id,
            body.system_role,
            administrator.id,
            administrator.username,
            body.current_password,
        )
    except _ADMINISTRATIVE_ERRORS as error:
        _raise_admin_error(error)


@router.get("/groups", response_model=AdministrativeGroupHealthListResponse)
def list_group_health(
    service: Annotated[AdministrativeService, Depends(get_administrative_service)],
) -> AdministrativeGroupHealthListResponse:
    return AdministrativeGroupHealthListResponse(
        items=[
            AdministrativeGroupHealthResponse.model_validate(item, from_attributes=True)
            for item in service.list_group_health()
        ]
    )


@router.patch(
    "/groups/{group_id}/administrator",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def assign_group_administrator(
    group_id: UUID,
    body: AdministrativeGroupAdministratorAssignment,
    administrator: Annotated[AuthenticatedUser, Depends(require_system_admin)],
    service: Annotated[AdministrativeService, Depends(get_administrative_service)],
) -> None:
    try:
        service.assign_group_administrator(
            group_id,
            body.user_id,
            administrator.id,
            administrator.username,
            body.current_password,
        )
    except _ADMINISTRATIVE_ERRORS as error:
        _raise_admin_error(error)


@router.get("/audit-events", response_model=AdministrativeAuditEventListResponse)
def list_audit_events(
    service: Annotated[AdministrativeService, Depends(get_administrative_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AdministrativeAuditEventListResponse:
    return AdministrativeAuditEventListResponse(
        items=[
            AdministrativeAuditEventResponse.model_validate(item, from_attributes=True)
            for item in service.list_audit_events(limit)
        ]
    )
