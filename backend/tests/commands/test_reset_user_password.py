from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.commands.reset_user_password import UserNotFoundError, read_password, reset_user_password


def test_reset_user_password_updates_hash_and_revokes_active_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = MagicMock()
    user_id = uuid4()
    reset_at = datetime(2026, 7, 16, 12, tzinfo=UTC)
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = user_id
    user_update_result = MagicMock()
    session_update_result = MagicMock(rowcount=2)
    connection.execute.side_effect = [select_result, user_update_result, session_update_result]
    hash_password = MagicMock(return_value="new-password-hash")
    monkeypatch.setattr("app.commands.reset_user_password.hash_password", hash_password)

    revoked_count = reset_user_password(
        connection,
        "family-user",
        "temporary-password",
        changed_at=reset_at,
    )

    assert revoked_count == 2
    assert connection.execute.call_count == 3
    hash_password.assert_called_once_with("temporary-password")
    user_update = connection.execute.call_args_list[1].args[0]
    assert user_update.compile().params["password_hash"] == "new-password-hash"
    assert user_update.compile().params["password_changed_at"] == reset_at
    session_update = connection.execute.call_args_list[2].args[0]
    assert session_update.compile().params["revoked_at"] == reset_at


def test_reset_user_password_rejects_unknown_user(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = MagicMock()
    connection.execute.return_value.scalar_one_or_none.return_value = None
    hash_password = MagicMock()
    monkeypatch.setattr("app.commands.reset_user_password.hash_password", hash_password)

    with pytest.raises(UserNotFoundError):
        reset_user_password(connection, "missing-user", "temporary-password")

    hash_password.assert_not_called()
    connection.execute.assert_called_once()


def test_read_password_uses_hidden_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    getpass = MagicMock(side_effect=["temporary-password", "temporary-password"])
    monkeypatch.setattr("app.commands.reset_user_password.getpass", getpass)

    assert read_password() == "temporary-password"
    assert getpass.call_count == 2


def test_read_password_rejects_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.commands.reset_user_password.getpass",
        MagicMock(side_effect=["temporary-password", "different-password"]),
    )

    with pytest.raises(SystemExit, match="Passwords do not match"):
        read_password()
