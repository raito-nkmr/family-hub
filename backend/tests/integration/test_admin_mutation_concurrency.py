import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.commands.set_user_role import set_user_role
from app.core.config import Settings
from app.features.audit.models import AdministrativeAuditEvent
from app.features.auth.admin_service import (
    AdministrativeService,
    UserOwnsGroupsWithoutAnotherAdminError,
)
from app.features.auth.models import SystemRole, User
from app.features.auth.passwords import hash_password
from app.features.auth.public import UserDirectory
from app.features.groups.models import FamilyGroup, FamilyGroupMember, GroupRole
from app.features.groups.service import GroupNotFoundError, GroupService

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def test_role_commands_serialize_without_removing_the_last_system_administrator() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    first_user_id = uuid4()
    second_user_id = uuid4()
    usernames = (f"role-race-first-{first_user_id.hex}", f"role-race-second-{second_user_id.hex}")
    start = Event()
    now = datetime.now(UTC)

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=first_user_id,
                    username=usernames[0],
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.ADMIN,
                    created_at=now,
                    password_changed_at=now,
                ),
                User(
                    id=second_user_id,
                    username=usernames[1],
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.ADMIN,
                    created_at=now,
                    password_changed_at=now,
                ),
            ]
        )
        session.commit()

    def demote(username: str) -> str:
        assert start.wait(timeout=5)
        with Session(engine) as session:
            try:
                set_user_role(session, username, SystemRole.USER)
            except SystemExit:
                return "rejected"
        return "changed"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(demote, username) for username in usernames]
            start.set()
            outcomes = [future.result(timeout=10) for future in futures]

        assert sorted(outcomes) == ["changed", "rejected"]
        with Session(engine) as session:
            active_admin_count = session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.system_role == SystemRole.ADMIN, User.is_active.is_(True))
            )
            assert active_admin_count == 1
    finally:
        with Session(engine) as session:
            session.execute(
                delete(AdministrativeAuditEvent).where(
                    AdministrativeAuditEvent.target_id.in_([str(first_user_id), str(second_user_id)])
                )
            )
            session.execute(delete(User).where(User.id.in_((first_user_id, second_user_id))))
            session.commit()
        engine.dispose()


def test_admin_mutations_serialize_without_removing_the_last_active_group_admin() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    first_user_id = uuid4()
    second_user_id = uuid4()
    group_id = uuid4()
    start = Event()
    now = datetime.now(UTC)
    settings = Settings(app_env="test", database_url=TEST_DATABASE_URL)

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=first_user_id,
                    username=f"admin-race-first-{first_user_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                User(
                    id=second_user_id,
                    username=f"admin-race-second-{second_user_id.hex}",
                    password_hash=hash_password("test-password"),
                    is_active=True,
                    system_role=SystemRole.ADMIN,
                    created_at=now,
                    password_changed_at=now,
                ),
                FamilyGroup(
                    id=group_id,
                    name=f"Admin race {group_id.hex}",
                    created_by_user_id=first_user_id,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.add_all(
            [
                FamilyGroupMember(group_id=group_id, user_id=first_user_id, role=GroupRole.ADMIN, joined_at=now),
                FamilyGroupMember(group_id=group_id, user_id=second_user_id, role=GroupRole.ADMIN, joined_at=now),
            ]
        )
        session.commit()

    def deactivate_first_user() -> None:
        assert start.wait(timeout=5)
        with Session(engine) as session:
            AdministrativeService(session, settings).update_user_status(
                first_user_id,
                False,
                second_user_id,
                "system-admin",
                "test-password",
            )

    def remove_second_group_admin() -> None:
        assert start.wait(timeout=5)
        with Session(engine) as session:
            GroupService(session, UserDirectory(session)).remove_member(
                group_id,
                second_user_id,
                first_user_id,
                f"admin-race-first-{first_user_id.hex}",
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(deactivate_first_user), executor.submit(remove_second_group_admin)]
            start.set()
            outcomes = []
            for future in futures:
                try:
                    future.result(timeout=10)
                except (GroupNotFoundError, UserOwnsGroupsWithoutAnotherAdminError) as error:
                    outcomes.append(error)

        assert len(outcomes) == 1
        with Session(engine) as session:
            active_admin_count = session.scalar(
                select(func.count())
                .select_from(FamilyGroupMember)
                .join(User, User.id == FamilyGroupMember.user_id)
                .where(
                    FamilyGroupMember.group_id == group_id,
                    FamilyGroupMember.role == GroupRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
            assert active_admin_count == 1
    finally:
        with Session(engine) as session:
            session.execute(delete(FamilyGroup).where(FamilyGroup.id == group_id))
            session.execute(delete(User).where(User.id.in_((first_user_id, second_user_id))))
            session.commit()
        engine.dispose()
