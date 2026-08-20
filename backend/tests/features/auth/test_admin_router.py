from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.features.auth.admin_router import assign_group_administrator, update_user_role, update_user_status
from app.features.auth.dependencies import AuthenticatedUser
from app.features.auth.models import SystemRole
from app.features.auth.schemas import (
    AdministrativeGroupAdministratorAssignment,
    AdministrativeUserRoleUpdate,
    AdministrativeUserStatusUpdate,
)

ADMINISTRATOR = AuthenticatedUser(id=uuid4(), username="administrator")


@pytest.mark.parametrize(
    ("handler", "body", "method"),
    [
        (
            update_user_status,
            AdministrativeUserStatusUpdate(is_active=False, current_password="password"),
            "update_user_status",
        ),
        (
            update_user_role,
            AdministrativeUserRoleUpdate(system_role=SystemRole.USER, current_password="password"),
            "update_user_role",
        ),
        (
            assign_group_administrator,
            AdministrativeGroupAdministratorAssignment(user_id=uuid4(), current_password="password"),
            "assign_group_administrator",
        ),
    ],
)
def test_admin_mutations_propagate_unexpected_exceptions(handler, body, method: str) -> None:
    service = MagicMock()
    getattr(service, method).side_effect = RuntimeError("unexpected failure")

    with pytest.raises(RuntimeError, match="unexpected failure"):
        handler(uuid4(), body, ADMINISTRATOR, service)
