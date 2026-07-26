from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user, require_csrf_token
from app.features.groups.dependencies import get_group_service
from app.features.groups.schemas import (
    GroupAdministrationOverviewResponse,
    GroupAuditEventListResponse,
    GroupAuditEventResponse,
    GroupCreate,
    GroupDetailResponse,
    GroupListResponse,
    GroupMemberAdd,
    GroupMemberCandidateListResponse,
    GroupMemberCandidateResponse,
    GroupMemberRemovalImpactResponse,
    GroupMemberRoleUpdate,
    GroupMembershipInvitationCreate,
    GroupMembershipInvitationDecision,
    GroupMembershipInvitationListResponse,
    GroupMembershipInvitationResponse,
    GroupResponse,
    GroupUpdate,
)
from app.features.groups.service import (
    GroupDetail,
    GroupForbiddenError,
    GroupMemberAlreadyExistsError,
    GroupMemberNotFoundError,
    GroupMembershipInvitationError,
    GroupNameAlreadyExistsError,
    GroupNotFoundError,
    GroupPersistenceError,
    GroupService,
    GroupUserNotFoundError,
    LastGroupAdminError,
)

router = APIRouter(tags=["groups"], dependencies=[Depends(require_authenticated_user)])


def _detail_response(detail: GroupDetail) -> GroupDetailResponse:
    return GroupDetailResponse(
        **GroupResponse.model_validate(detail.group).model_dump(),
        members=detail.members,
    )


def _raise_member_error(error: Exception) -> NoReturn:
    if isinstance(error, GroupNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found") from error
    if isinstance(error, (GroupMemberNotFoundError, GroupUserNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error
    if isinstance(error, GroupForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group administrator required") from error
    if isinstance(error, GroupMemberAlreadyExistsError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a group member") from error
    if isinstance(error, LastGroupAdminError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group must have an active administrator",
        ) from error
    if isinstance(error, GroupPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update group membership",
        ) from error
    raise error


@router.get("", response_model=GroupListResponse)
def list_groups(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupListResponse:
    return GroupListResponse(
        items=[GroupResponse.model_validate(group) for group in service.list_groups(authenticated_user.id)]
    )


@router.post(
    "",
    response_model=GroupDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_group(
    body: GroupCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupDetailResponse:
    try:
        return _detail_response(service.create_group(body.name, authenticated_user.id, authenticated_user.username))
    except GroupNameAlreadyExistsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group name already exists") from error
    except GroupPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create group",
        ) from error


@router.get("/membership-invitations", response_model=GroupMembershipInvitationListResponse)
def list_my_group_membership_invitations(
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupMembershipInvitationListResponse:
    return GroupMembershipInvitationListResponse(
        items=[
            GroupMembershipInvitationResponse(
                id=invitation.id,
                group_id=invitation.group_id,
                group_name=group_name,
                user_id=invitation.user_id,
                username=authenticated_user.username,
                role=invitation.role,
                status=invitation.status,
                created_at=invitation.created_at,
            )
            for invitation, group_name in service.list_my_membership_invitations(authenticated_user.id)
        ]
    )


@router.post(
    "/membership-invitations/{invitation_id}/decision",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def decide_group_membership_invitation(
    invitation_id: UUID,
    body: GroupMembershipInvitationDecision,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> Response:
    try:
        service.decide_membership_invitation(
            invitation_id,
            authenticated_user.id,
            authenticated_user.username,
            body.accept,
        )
    except GroupMembershipInvitationError as error:
        raise HTTPException(status_code=404, detail="Group invitation not found") from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupDetailResponse:
    try:
        return _detail_response(service.get_group(group_id, authenticated_user.id))
    except GroupNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found") from error


@router.patch(
    "/{group_id}",
    response_model=GroupDetailResponse,
    dependencies=[Depends(require_csrf_token)],
)
def rename_group(
    group_id: UUID,
    body: GroupUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupDetailResponse:
    try:
        return _detail_response(
            service.rename_group(group_id, authenticated_user.id, authenticated_user.username, body.name)
        )
    except GroupNameAlreadyExistsError as error:
        raise HTTPException(status_code=409, detail="Group name already exists") from error
    except (GroupNotFoundError, GroupForbiddenError, GroupPersistenceError) as error:
        _raise_member_error(error)


@router.get("/{group_id}/administration", response_model=GroupAdministrationOverviewResponse)
def get_group_administration_overview(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupAdministrationOverviewResponse:
    try:
        return GroupAdministrationOverviewResponse.model_validate(
            service.administration_overview(group_id, authenticated_user.id)
        )
    except (GroupNotFoundError, GroupForbiddenError) as error:
        _raise_member_error(error)


@router.get("/{group_id}/audit-events", response_model=GroupAuditEventListResponse)
def list_group_audit_events(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupAuditEventListResponse:
    try:
        events = service.list_group_audit_events(group_id, authenticated_user.id)
    except (GroupNotFoundError, GroupForbiddenError) as error:
        _raise_member_error(error)
    return GroupAuditEventListResponse(
        items=[GroupAuditEventResponse.model_validate(event, from_attributes=True) for event in events]
    )


@router.get("/{group_id}/member-candidates", response_model=GroupMemberCandidateListResponse)
def list_group_member_candidates(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupMemberCandidateListResponse:
    try:
        candidates = service.list_member_candidates(group_id, authenticated_user.id)
    except (GroupNotFoundError, GroupForbiddenError) as error:
        _raise_member_error(error)
    return GroupMemberCandidateListResponse(
        items=[GroupMemberCandidateResponse(user_id=user.id, username=user.username) for user in candidates]
    )


@router.post(
    "/{group_id}/membership-invitations",
    response_model=GroupMembershipInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def invite_group_member(
    group_id: UUID,
    body: GroupMembershipInvitationCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupMembershipInvitationResponse:
    try:
        invitation, user = service.invite_member(
            group_id,
            authenticated_user.id,
            authenticated_user.username,
            body.user_id,
            body.role,
        )
        return GroupMembershipInvitationResponse(
            id=invitation.id,
            group_id=group_id,
            group_name=service.get_group(group_id, authenticated_user.id).group.name,
            user_id=user.id,
            username=user.username,
            role=invitation.role,
            status=invitation.status,
            created_at=invitation.created_at,
        )
    except GroupMembershipInvitationError as error:
        raise HTTPException(status_code=409, detail="A pending invitation already exists") from error
    except (
        GroupNotFoundError,
        GroupUserNotFoundError,
        GroupForbiddenError,
        GroupMemberAlreadyExistsError,
    ) as error:
        _raise_member_error(error)


@router.post(
    "/{group_id}/members",
    response_model=GroupDetailResponse,
    dependencies=[Depends(require_csrf_token)],
)
def add_group_member(
    group_id: UUID,
    body: GroupMemberAdd,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupDetailResponse:
    try:
        return _detail_response(
            service.add_member(
                group_id,
                authenticated_user.id,
                body.user_id,
                body.role,
                authenticated_user.username,
            )
        )
    except (
        GroupNotFoundError,
        GroupUserNotFoundError,
        GroupForbiddenError,
        GroupMemberAlreadyExistsError,
        GroupPersistenceError,
    ) as error:
        _raise_member_error(error)


@router.patch(
    "/{group_id}/members/{user_id}",
    response_model=GroupDetailResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_group_member_role(
    group_id: UUID,
    user_id: UUID,
    body: GroupMemberRoleUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupDetailResponse:
    try:
        return _detail_response(
            service.update_member_role(
                group_id,
                user_id,
                authenticated_user.id,
                body.role,
                authenticated_user.username,
            )
        )
    except (
        GroupNotFoundError,
        GroupMemberNotFoundError,
        GroupForbiddenError,
        LastGroupAdminError,
        GroupPersistenceError,
    ) as error:
        _raise_member_error(error)


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> Response:
    try:
        service.remove_member(group_id, user_id, authenticated_user.id, authenticated_user.username)
    except (
        GroupNotFoundError,
        GroupMemberNotFoundError,
        GroupForbiddenError,
        LastGroupAdminError,
        GroupPersistenceError,
    ) as error:
        _raise_member_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{group_id}/members/{user_id}/removal-impact",
    response_model=GroupMemberRemovalImpactResponse,
)
def get_group_member_removal_impact(
    group_id: UUID,
    user_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupMemberRemovalImpactResponse:
    try:
        return GroupMemberRemovalImpactResponse.model_validate(
            service.member_removal_impact(group_id, user_id, authenticated_user.id)
        )
    except (GroupNotFoundError, GroupMemberNotFoundError, GroupForbiddenError) as error:
        _raise_member_error(error)
