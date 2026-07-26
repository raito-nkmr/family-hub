import argparse
from unittest.mock import MagicMock

import pytest

from app.commands.create_dummy_users import (
    MAXIMUM_USER_COUNT,
    build_dummy_user_specs,
    create_dummy_users,
    positive_user_count,
    validate_development_environment,
)
from app.core.config import Settings
from app.features.auth.models import SystemRole


def test_build_dummy_user_specs_creates_admin_and_numbered_users() -> None:
    specs = build_dummy_user_specs(3, " Family ", " DUMMY-ADMIN ")

    assert [(spec.username, spec.system_role) for spec in specs] == [
        ("dummy-admin", SystemRole.ADMIN),
        ("family-01", SystemRole.USER),
        ("family-02", SystemRole.USER),
        ("family-03", SystemRole.USER),
    ]


@pytest.mark.parametrize("value", ["0", str(MAXIMUM_USER_COUNT + 1)])
def test_positive_user_count_rejects_out_of_range_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="count must be between"):
        positive_user_count(value)


def test_create_dummy_users_inserts_missing_users_and_skips_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = MagicMock()
    connection.execute.return_value.scalars.return_value = ["dummy-user-01"]
    hash_password = MagicMock(side_effect=["admin-hash", "user-hash"])
    monkeypatch.setattr("app.commands.create_dummy_users.hash_password", hash_password)
    specs = build_dummy_user_specs(2, "dummy-user", "dummy-admin")

    result = create_dummy_users(connection, specs, "shared-development-password")

    assert result.created_usernames == ("dummy-admin", "dummy-user-02")
    assert result.skipped_usernames == ("dummy-user-01",)
    assert connection.execute.call_count == 3
    assert hash_password.call_count == 2


def test_validate_development_environment_rejects_non_development_environment() -> None:
    with pytest.raises(SystemExit, match="available only"):
        validate_development_environment(Settings(app_env="production", auth_cookie_secure=True))
