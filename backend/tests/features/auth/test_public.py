from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.features.auth.public import PublicUser, UserDirectory


def test_user_directory_returns_minimal_public_users() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    session.execute.return_value.all.return_value = [(user_id, "owner", True)]
    directory = UserDirectory(session)

    result = directory.list_by_ids({user_id})

    assert result[user_id].username == "owner"
    assert result[user_id].is_active is True


def test_user_directory_lists_active_users() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    session.execute.return_value.all.return_value = [(user_id, "たろう", True)]
    directory = UserDirectory(session)

    result = directory.list_active()

    assert result == [PublicUser(id=user_id, username="たろう", is_active=True)]
