from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_csrf_token,
    require_password_change_complete,
    require_system_admin,
    require_trusted_origin,
)
from app.features.auth.invitation_dependencies import get_invitation_service
from app.features.auth.invitations import (
    CreatedInvitation,
    InvitationNotFoundError,
    InvitationPersistenceError,
    InvitationService,
    InvitationSummary,
    InvitationUnavailableError,
    InvitationUsernameUnavailableError,
)
from app.features.auth.schemas import (
    InvitationAccept,
    InvitationCreate,
    InvitationCreatedResponse,
    InvitationListResponse,
    InvitationResponse,
    UserResponse,
)

public_router = APIRouter(tags=["auth invitations"])
admin_router = APIRouter(
    tags=["admin invitations"],
    dependencies=[Depends(require_system_admin), Depends(require_password_change_complete)],
)


def _response(invitation: InvitationSummary) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        username=invitation.username,
        created_by_username=invitation.created_by_username,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        status=invitation.status,
    )


def _created_response(created: CreatedInvitation) -> InvitationCreatedResponse:
    invitation = created.invitation
    return InvitationCreatedResponse(
        id=invitation.id,
        username=invitation.username,
        created_by_username=invitation.created_by_username,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        status=invitation.status,
        token=created.token,
    )


@admin_router.get("", response_model=InvitationListResponse)
def list_invitations(
    service: Annotated[InvitationService, Depends(get_invitation_service)],
    q: Annotated[str | None, Query(max_length=64)] = None,
    invitation_status: Annotated[str | None, Query(alias="status")] = None,
) -> InvitationListResponse:
    return InvitationListResponse(
        items=[_response(invitation) for invitation in service.list_invitations(q, invitation_status)]
    )


@admin_router.post(
    "",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_invitation(
    body: InvitationCreate,
    administrator: Annotated[AuthenticatedUser, Depends(require_system_admin)],
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> InvitationCreatedResponse:
    try:
        return _created_response(
            service.create_invitation(
                body.username,
                administrator.id,
                administrator.username,
                body.expires_in_hours,
            )
        )
    except InvitationUsernameUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is unavailable") from error
    except InvitationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create invitation",
        ) from error


@admin_router.delete(
    "/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def revoke_invitation(
    invitation_id: UUID,
    administrator: Annotated[AuthenticatedUser, Depends(require_system_admin)],
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> Response:
    try:
        service.revoke_invitation(invitation_id, administrator.id, administrator.username)
    except InvitationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found") from error
    except InvitationUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation has already been used") from error
    except InvitationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not revoke invitation",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.delete(
    "/history/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def remove_invitation_history(
    invitation_id: UUID,
    administrator: Annotated[AuthenticatedUser, Depends(require_system_admin)],
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> Response:
    try:
        service.remove_invitation_history(
            invitation_id,
            administrator.id,
            administrator.username,
        )
    except InvitationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found") from error
    except InvitationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not remove invitation history",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@public_router.post(
    "/accept",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def accept_invitation(
    body: InvitationAccept,
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> UserResponse:
    try:
        user = service.accept_invitation(body.token, body.password)
    except InvitationUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation is invalid or expired",
        ) from error
    except InvitationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not accept invitation",
        ) from error
    return UserResponse(id=user.id, username=user.username, system_role=user.system_role)
