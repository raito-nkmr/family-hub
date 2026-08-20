from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.auth.dependencies import AuthenticatedUser, require_csrf_token, require_system_admin
from app.features.auth.invitation_router import accept_invitation, create_invitation, revoke_invitation
from app.features.auth.invitations import (
    CreatedInvitation,
    InvitationSummary,
    InvitationUnavailableError,
    InvitationUsernameUnavailableError,
)
from app.features.auth.models import SystemRole
from app.features.auth.schemas import InvitationAccept, InvitationCreate
from app.main import create_app
from tests.features.auth.factories import make_user


def make_summary() -> InvitationSummary:
    now = datetime.now(UTC)
    return InvitationSummary(
        id=uuid4(),
        username="family-member",
        created_by_username="owner",
        created_at=now,
        expires_at=now + timedelta(days=1),
        status="pending",
    )


class InvitationServiceStub:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.revoked = False

    def create_invitation(self, username, creator_user_id, creator_username, expires_in_hours=24):
        if self.error:
            raise self.error
        return CreatedInvitation(make_summary(), "token" * 8)

    def revoke_invitation(self, invitation_id, actor_user_id, actor_username):
        if self.error:
            raise self.error
        self.revoked = True

    def accept_invitation(self, token, password):
        if self.error:
            raise self.error
        return make_user()


ADMIN = AuthenticatedUser(id=uuid4(), username="owner", system_role=SystemRole.ADMIN)


def test_admin_creates_invitation() -> None:
    response = create_invitation(InvitationCreate(username="family-member"), ADMIN, InvitationServiceStub())

    assert response.username == "family-member"
    assert response.token


def test_duplicate_invitation_username_returns_conflict() -> None:
    with pytest.raises(HTTPException) as error:
        create_invitation(
            InvitationCreate(username="family-member"),
            ADMIN,
            InvitationServiceStub(error=InvitationUsernameUnavailableError()),
        )

    assert error.value.status_code == 409


def test_invalid_invitation_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        accept_invitation(
            InvitationAccept(token="t" * 43, password="a-secure-family-password"),
            InvitationServiceStub(error=InvitationUnavailableError()),
        )

    assert error.value.status_code == 400


def test_admin_revokes_invitation() -> None:
    service = InvitationServiceStub()

    response = revoke_invitation(uuid4(), ADMIN, service)

    assert response.status_code == 204
    assert service.revoked is True


def test_invitation_routes_have_expected_security_dependencies() -> None:
    paths = create_app(Settings(app_env="test")).openapi()["paths"]

    assert "post" in paths["/api/v1/auth/invitations/accept"]
    assert {"get", "post"} <= set(paths["/api/v1/admin/invitations"])
    assert "delete" in paths["/api/v1/admin/invitations/{invitation_id}"]
    assert "delete" in paths["/api/v1/admin/invitations/history/{invitation_id}"]

    from app.features.auth.invitation_router import admin_router

    assert any(dependency.dependency is require_system_admin for dependency in admin_router.dependencies)
    mutations = [route for route in admin_router.routes if route.methods & {"POST", "DELETE"}]
    assert all(
        any(dependency.dependency is require_csrf_token for dependency in route.dependencies) for route in mutations
    )
