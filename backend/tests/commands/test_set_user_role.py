from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.commands.set_user_role import set_user_role
from app.features.auth.models import SystemRole, User


def make_user(role: SystemRole) -> User:
    return User(
        id=uuid4(),
        username="owner",
        password_hash="password-hash",
        is_active=True,
        system_role=role,
    )


def test_set_user_role_acquires_administrator_lock_before_reading_user() -> None:
    session = MagicMock(spec=Session)
    user = make_user(SystemRole.ADMIN)
    session.scalar.side_effect = [user, 1]

    set_user_role(session, "owner", SystemRole.USER)

    assert session.method_calls[0][0] == "execute"
    assert user.system_role is SystemRole.USER
    session.commit.assert_called_once_with()


def test_set_user_role_rejects_demoting_last_active_administrator() -> None:
    session = MagicMock(spec=Session)
    user = make_user(SystemRole.ADMIN)
    session.scalar.side_effect = [user, 0]

    with pytest.raises(SystemExit, match="last active system administrator"):
        set_user_role(session, "owner", SystemRole.USER)

    assert user.system_role is SystemRole.ADMIN
    session.commit.assert_not_called()
