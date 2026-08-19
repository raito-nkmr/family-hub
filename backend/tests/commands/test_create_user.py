from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.commands.create_user import create_user
from app.features.auth.models import SystemRole


def execute_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_create_user_rejects_first_regular_user() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [execute_result(None), execute_result(None)]

    with pytest.raises(SystemExit, match="active system administrator"):
        create_user(connection, "member", "password-hash", SystemRole.USER)

    assert connection.execute.call_count == 2


def test_create_user_allows_first_system_administrator() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [execute_result(None), MagicMock()]

    create_user(connection, "owner", "password-hash", SystemRole.ADMIN)

    assert connection.execute.call_count == 2


def test_create_user_allows_regular_user_after_active_administrator_exists() -> None:
    connection = MagicMock()
    connection.execute.side_effect = [execute_result(None), execute_result(uuid4()), MagicMock()]

    create_user(connection, "member", "password-hash", SystemRole.USER)

    assert connection.execute.call_count == 3


def test_create_user_rejects_duplicate_username() -> None:
    connection = MagicMock()
    connection.execute.return_value = execute_result(uuid4())

    with pytest.raises(SystemExit, match="already exists"):
        create_user(connection, "owner", "password-hash", SystemRole.ADMIN)

    connection.execute.assert_called_once()
