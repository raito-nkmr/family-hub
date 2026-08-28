import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.features.auth.models import SystemRole, User
from app.features.auth.public import UserDirectory
from app.features.chores.models import ChoreCategory, ChoreTask
from app.features.chores.service import ChoreNotFoundError, ChoreService
from app.features.groups.models import FamilyGroup, FamilyGroupMember, FamilyGroupMembershipInvitation, GroupRole
from app.features.groups.service import GroupMembershipInvitationError, GroupService
from app.features.notifications.models import NotificationType
from app.features.notifications.public import enqueue_group_notification
from app.features.photos.schemas import UploadFileCreate
from app.features.photos.storage.facade import PhotoStorage
from app.features.photos.uploads import UploadBatchInvalidError, UploadBatchService
from app.features.shopping.models import ShoppingItem
from app.features.shopping.service import ShoppingNotFoundError, ShoppingService

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(TEST_DATABASE_URL is None, reason="TEST_DATABASE_URL is not configured"),
]


def test_concurrent_invitation_acceptance_inserts_one_membership() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    actor_id = uuid4()
    target_id = uuid4()
    group_id = uuid4()
    invitation_id = uuid4()
    now = datetime.now(UTC)

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=actor_id,
                    username=f"membership-admin-{actor_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                User(
                    id=target_id,
                    username=f"membership-target-{target_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                FamilyGroup(
                    id=group_id,
                    name=f"Membership race {group_id.hex}",
                    created_by_user_id=actor_id,
                    created_at=now,
                    updated_at=now,
                ),
                FamilyGroupMember(group_id=group_id, user_id=actor_id, role=GroupRole.ADMIN, joined_at=now),
                FamilyGroupMembershipInvitation(
                    id=invitation_id,
                    group_id=group_id,
                    invitee_user_id=target_id,
                    invited_by_user_id=actor_id,
                    role=GroupRole.MEMBER,
                    status="pending",
                    created_at=now,
                    responded_at=None,
                ),
            ]
        )
        session.commit()

    start = Event()

    def accept_invitation() -> str:
        assert start.wait(timeout=5)
        with Session(engine) as session:
            try:
                GroupService(session, UserDirectory(session)).decide_membership_invitation(
                    invitation_id,
                    target_id,
                    f"membership-target-{target_id.hex}",
                    True,
                )
            except GroupMembershipInvitationError:
                return "invitation-not-pending"
        return "accepted"

    def accept_invitation_again() -> str:
        assert start.wait(timeout=5)
        with Session(engine) as session:
            try:
                GroupService(session, UserDirectory(session)).decide_membership_invitation(
                    invitation_id,
                    target_id,
                    f"membership-target-{target_id.hex}",
                    True,
                )
            except GroupMembershipInvitationError:
                return "invitation-not-pending"
        return "accepted"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(accept_invitation), executor.submit(accept_invitation_again)]
            start.set()
            outcomes = [future.result(timeout=10) for future in futures]

        assert sorted(outcomes) == ["accepted", "invitation-not-pending"]
        with Session(engine) as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(FamilyGroupMember)
                    .where(FamilyGroupMember.group_id == group_id, FamilyGroupMember.user_id == target_id)
                )
                == 1
            )
    finally:
        with Session(engine) as session:
            session.execute(delete(FamilyGroup).where(FamilyGroup.id == group_id))
            session.execute(delete(User).where(User.id.in_((actor_id, target_id))))
            session.commit()
        engine.dispose()


@pytest.mark.parametrize("resource_kind", ["shopping", "chore"])
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
            category_id = uuid4()
            session.add(
                ChoreCategory(
                    id=category_id,
                    group_id=group_id,
                    name="浴室",
                    sort_order=0,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            session.add(
                ChoreTask(
                    id=resource_id,
                    group_id=group_id,
                    task_name="Kitchen",
                    category_id=category_id,
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
                with pytest.raises(ChoreNotFoundError):
                    ChoreService(session, UserDirectory(session)).complete_task(resource_id, user_id)

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


def test_upload_batch_rechecks_membership_after_group_lock() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    owner_id = uuid4()
    admin_id = uuid4()
    group_id = uuid4()
    now = datetime.now(UTC)

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    username=f"upload-owner-{owner_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                User(
                    id=admin_id,
                    username=f"upload-admin-{admin_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                FamilyGroup(
                    id=group_id,
                    name=f"Upload race {group_id.hex}",
                    created_by_user_id=admin_id,
                    created_at=now,
                    updated_at=now,
                ),
                FamilyGroupMember(group_id=group_id, user_id=admin_id, role=GroupRole.ADMIN, joined_at=now),
                FamilyGroupMember(group_id=group_id, user_id=owner_id, role=GroupRole.MEMBER, joined_at=now),
            ]
        )
        session.commit()

    group_locked = Event()
    action_started = Event()
    release_removal = Event()
    storage = MagicMock(spec=PhotoStorage)
    storage.maximum_upload_bytes = 1_024

    def remove_membership() -> None:
        with Session(engine) as session:
            session.scalar(select(FamilyGroup).where(FamilyGroup.id == group_id).with_for_update())
            group_locked.set()
            assert release_removal.wait(timeout=5)
            membership = session.get(FamilyGroupMember, (group_id, owner_id))
            assert membership is not None
            session.delete(membership)
            session.commit()

    def create_upload_batch() -> str:
        assert group_locked.wait(timeout=5)
        action_started.set()
        with Session(engine) as session:
            service = UploadBatchService(session, storage, "Asia/Tokyo")
            with pytest.raises(UploadBatchInvalidError):
                service.create_batch(
                    owner_id,
                    [
                        UploadFileCreate(
                            client_id="client-1",
                            original_filename="photo.jpg",
                            declared_content_type="image/jpeg",
                            size_bytes=5,
                        )
                    ],
                    {group_id},
                )
        return "membership-rechecked"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            removal_future = executor.submit(remove_membership)
            upload_future = executor.submit(create_upload_batch)
            assert action_started.wait(timeout=5)
            release_removal.set()
            removal_future.result(timeout=5)
            assert upload_future.result(timeout=5) == "membership-rechecked"
    finally:
        release_removal.set()
        with Session(engine) as session:
            session.execute(delete(FamilyGroup).where(FamilyGroup.id == group_id))
            session.execute(delete(User).where(User.id.in_((owner_id, admin_id))))
            session.commit()
        engine.dispose()


def test_group_notification_reads_members_after_membership_removal_commits() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-c timezone=UTC"})
    owner_id = uuid4()
    admin_id = uuid4()
    group_id = uuid4()
    now = datetime.now(UTC)

    with Session(engine) as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    username=f"notification-owner-{owner_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                User(
                    id=admin_id,
                    username=f"notification-admin-{admin_id.hex}",
                    password_hash="unused",
                    is_active=True,
                    system_role=SystemRole.USER,
                    created_at=now,
                    password_changed_at=now,
                ),
                FamilyGroup(
                    id=group_id,
                    name=f"Notification race {group_id.hex}",
                    created_by_user_id=admin_id,
                    created_at=now,
                    updated_at=now,
                ),
                FamilyGroupMember(group_id=group_id, user_id=admin_id, role=GroupRole.ADMIN, joined_at=now),
                FamilyGroupMember(group_id=group_id, user_id=owner_id, role=GroupRole.MEMBER, joined_at=now),
            ]
        )
        session.commit()

    group_locked = Event()
    action_started = Event()
    release_removal = Event()

    def remove_membership() -> None:
        with Session(engine) as session:
            session.scalar(select(FamilyGroup).where(FamilyGroup.id == group_id).with_for_update())
            group_locked.set()
            assert release_removal.wait(timeout=5)
            membership = session.get(FamilyGroupMember, (group_id, owner_id))
            assert membership is not None
            session.delete(membership)
            session.commit()

    def enqueue_notification() -> int:
        assert group_locked.wait(timeout=5)
        action_started.set()
        with Session(engine) as session:
            return enqueue_group_notification(
                session,
                {group_id},
                NotificationType.PHOTO_SHARED,
                f"notification-race:{group_id}",
                {"url": "/photos/new"},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            removal_future = executor.submit(remove_membership)
            notification_future = executor.submit(enqueue_notification)
            assert action_started.wait(timeout=5)
            release_removal.set()
            removal_future.result(timeout=5)
            assert notification_future.result(timeout=5) == 1
    finally:
        release_removal.set()
        with Session(engine) as session:
            session.execute(delete(FamilyGroup).where(FamilyGroup.id == group_id))
            session.execute(delete(User).where(User.id.in_((owner_id, admin_id))))
            session.commit()
        engine.dispose()
