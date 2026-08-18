from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.invitations import (
    InvitationService,
    InvitationUnavailableError,
    InvitationUsernameUnavailableError,
    hash_invitation_token,
)
from app.features.auth.models import SystemRole, UserInvitation


def make_invitation(*, expired: bool = False) -> UserInvitation:
    now = datetime.now(UTC)
    return UserInvitation(
        id=uuid4(),
        username="family-member",
        token_hash=hash_invitation_token("invitation-token"),
        created_by_user_id=uuid4(),
        created_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1) if expired else now + timedelta(hours=1),
        used_at=None,
        revoked_at=None,
    )


def make_service(session: MagicMock) -> InvitationService:
    return InvitationService(session, Settings(app_env="test"))


def test_create_invitation_hashes_token_and_revokes_previous_invite() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None
    service = make_service(session)

    created = service.create_invitation("family-member", uuid4(), "owner")

    invitation = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], UserInvitation))
    assert isinstance(invitation, UserInvitation)
    assert invitation.token_hash == hash_invitation_token(created.token)
    assert created.invitation.status == "pending"
    assert created.invitation.created_by_username == "owner"
    session.execute.assert_called_once()
    session.commit.assert_called_once_with()


def test_create_invitation_rejects_existing_user() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = uuid4()

    with pytest.raises(InvitationUsernameUnavailableError):
        make_service(session).create_invitation("family-member", uuid4(), "owner")

    session.add.assert_not_called()


def test_remove_invitation_history_deletes_record_and_commits() -> None:
    session = MagicMock(spec=Session)
    invitation = make_invitation()
    session.scalar.return_value = invitation

    make_service(session).remove_invitation_history(invitation.id, uuid4(), "owner")

    session.delete.assert_called_once_with(invitation)
    session.commit.assert_called_once_with()


def test_accept_invitation_creates_regular_user(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    invitation = make_invitation()
    session.scalar.side_effect = [invitation, None]
    monkeypatch.setattr("app.features.auth.invitations.hash_password", lambda password: f"hashed:{password}")

    user = make_service(session).accept_invitation("invitation-token", "a-secure-family-password")

    assert user.username == "family-member"
    assert user.password_hash == "hashed:a-secure-family-password"
    assert user.system_role is SystemRole.USER
    assert user.must_change_password is False
    assert invitation.used_at is not None
    session.commit.assert_called_once_with()


def test_accept_invitation_rejects_expired_token() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = make_invitation(expired=True)

    with pytest.raises(InvitationUnavailableError):
        make_service(session).accept_invitation("invitation-token", "a-secure-family-password")

    session.add.assert_not_called()
    session.commit.assert_not_called()
