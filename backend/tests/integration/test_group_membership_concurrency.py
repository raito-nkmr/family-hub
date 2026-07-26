import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.features.auth.models import SystemRole, User
from app.features.auth.public import UserDirectory
from app.features.cleaning.models import CleaningTask
from app.features.cleaning.service import CleaningNotFoundError, CleaningService
from app.features.groups.models import FamilyGroup, FamilyGroupMember, GroupRole
from app.features.shopping.models import ShoppingItem
from app.features.shopping.service import ShoppingNotFoundError, ShoppingService

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


@pytest.mark.parametrize("resource_kind", ["shopping", "cleaning"])
def test_member_action_cannot_commit_after_membership_removal(resource_kind: str) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    user_id = uuid4()
    group_id = uuid4()
    resource_id = uuid4()
    group_locked = Event()
    release_removal = Event()
    action_started = Event()

    with Session(engine) as session:
        session.add(
            User(
                id=user_id,
                username=f"membership-race-{user_id.hex}",
                password_hash="unused-in-this-test",
                is_active=True,
                system_role=SystemRole.USER,
                created_at=datetime.now(UTC),
                password_changed_at=datetime.now(UTC),
            )
        )
        session.flush()
        session.add(
            FamilyGroup(
                id=group_id,
                name=f"Concurrency {group_id.hex}",
                created_by_user_id=user_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        session.flush()
        session.add(
            FamilyGroupMember(
                group_id=group_id,
                user_id=user_id,
                role=GroupRole.MEMBER,
                joined_at=datetime.now(UTC),
            )
        )
        if resource_kind == "shopping":
            session.add(
                ShoppingItem(
                    id=resource_id,
                    group_id=group_id,
                    name="Milk",
                    created_by_user_id=user_id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        else:
            session.add(
                CleaningTask(
                    id=resource_id,
                    group_id=group_id,
                    name="Kitchen",
                    interval_days=1,
                    is_active=True,
                    created_by_user_id=user_id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
        session.commit()

    def remove_membership_while_holding_group_lock() -> None:
        with Session(engine) as session:
            group = session.scalar(select(FamilyGroup).where(FamilyGroup.id == group_id).with_for_update())
            assert group is not None
            group_locked.set()
            assert release_removal.wait(timeout=5)
            membership = session.get(FamilyGroupMember, (group_id, user_id))
            assert membership is not None
            session.delete(membership)
            session.commit()

    def attempt_member_action() -> None:
        assert group_locked.wait(timeout=5)
        action_started.set()
        with Session(engine) as session:
            if resource_kind == "shopping":
                with pytest.raises(ShoppingNotFoundError):
                    ShoppingService(session, UserDirectory(session)).purchase_item(resource_id, user_id)
            else:
                with pytest.raises(CleaningNotFoundError):
                    CleaningService(session, UserDirectory(session)).complete_task(resource_id, user_id)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            removal_future = executor.submit(remove_membership_while_holding_group_lock)
            action_future = executor.submit(attempt_member_action)
            assert action_started.wait(timeout=5)
            release_removal.set()
            removal_future.result(timeout=5)
            action_future.result(timeout=5)
    finally:
        release_removal.set()
        with Session(engine) as session:
            session.execute(delete(FamilyGroup).where(FamilyGroup.id == group_id))
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()
