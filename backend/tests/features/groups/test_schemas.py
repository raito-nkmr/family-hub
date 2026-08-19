from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.features.groups.models import GroupRole
from app.features.groups.schemas import GroupCreate, GroupResponse
from app.features.groups.service import GroupSummary


def test_group_create_trims_name() -> None:
    assert GroupCreate(name="  同居家族  ").name == "同居家族"


def test_group_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError, match="group name must not be blank"):
        GroupCreate(name="   ")


def test_group_response_normalizes_datetimes_to_utc() -> None:
    jst = timezone(timedelta(hours=9))
    summary = GroupSummary(
        id=uuid4(),
        name="同居家族",
        created_by_user_id=uuid4(),
        created_at=datetime(2026, 7, 15, 12, tzinfo=jst),
        updated_at=datetime(2026, 7, 15, 13, tzinfo=jst),
        current_user_role=GroupRole.ADMIN,
        member_count=1,
    )

    response = GroupResponse.model_validate(summary)

    assert response.created_at == datetime(2026, 7, 15, 3, tzinfo=UTC)
    assert response.updated_at == datetime(2026, 7, 15, 4, tzinfo=UTC)
