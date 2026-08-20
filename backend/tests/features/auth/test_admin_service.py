from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.features.auth.admin_service import AdministrativeService
from app.features.auth.models import SystemRole
from tests.features.auth.factories import make_user


def test_reauthenticate_locks_and_refreshes_the_administrator(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock(spec=Session)
    administrator = make_user()
    administrator.system_role = SystemRole.ADMIN
    session.scalar.return_value = administrator
    verify = MagicMock(return_value=True)
    monkeypatch.setattr("app.features.auth.admin_service.verify_password", verify)

    result = AdministrativeService(session, Settings(app_env="test"))._reauthenticate(
        administrator.id, "current password"
    )

    assert result is administrator
    statement = session.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert statement.get_execution_options()["populate_existing"] is True
    verify.assert_called_once_with("current password", administrator.password_hash)
