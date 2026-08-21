from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.auth.public import PublicUser, UserDirectory
from app.features.chores.models import ChoreCategory, ChoreCompletion, ChoreTask
from app.features.chores.service import (
    ChoreCategoryDuplicateError,
    ChoreCategoryInUseError,
    ChoreCategoryOrderInvalidError,
    ChoreForbiddenError,
    ChoreInactiveTaskError,
    ChoreNotFoundError,
    ChoreService,
)
from app.features.groups.models import GroupRole
from tests.features.chores.factories import make_chore_category, make_chore_task, make_completion
from tests.features.groups.factories import make_membership


def make_service(session: Session) -> tuple[ChoreService, MagicMock]:
    directory = MagicMock(spec=UserDirectory)
    return ChoreService(session, directory), directory


def test_member_can_create_chore_category() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    session.get.return_value = make_membership(group_id, user_id, role=GroupRole.MEMBER)
    session.scalars.return_value.all.return_value = [group_id]
    session.scalar.return_value = None
    service, _ = make_service(session)

    result = service.create_category(group_id, user_id, "  2階  ")

    category = session.add.call_args.args[0]
    assert isinstance(category, ChoreCategory)
    assert category.group_id == group_id
    assert category.name == "2階"
    assert result.name == "2階"
    session.commit.assert_called_once_with()


def test_duplicate_chore_category_is_rejected() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    session.get.return_value = make_membership(group_id, user_id, role=GroupRole.MEMBER)
    session.scalars.return_value.all.return_value = [group_id]
    session.scalar.return_value = uuid4()
    service, _ = make_service(session)

    with pytest.raises(ChoreCategoryDuplicateError):
        service.create_category(group_id, user_id, "浴室")

    session.add.assert_not_called()


def test_member_can_reorder_chore_categories() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    first = make_chore_category(group_id=group_id, name="1階", sort_order=0)
    second = make_chore_category(group_id=group_id, name="2階", sort_order=1)
    session.get.return_value = make_membership(group_id, user_id, role=GroupRole.MEMBER)
    session.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[group_id])),
        MagicMock(all=MagicMock(return_value=[first, second])),
    ]
    service, _ = make_service(session)

    result = service.reorder_categories(group_id, user_id, [second.id, first.id])

    assert [category.id for category in result] == [second.id, first.id]
    assert second.sort_order == 0
    assert first.sort_order == 1
    session.commit.assert_called_once_with()


def test_reorder_rejects_category_from_another_group() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    category = make_chore_category(group_id=group_id)
    session.get.return_value = make_membership(group_id, user_id, role=GroupRole.MEMBER)
    session.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[group_id])),
        MagicMock(all=MagicMock(return_value=[category])),
    ]
    service, _ = make_service(session)

    with pytest.raises(ChoreCategoryOrderInvalidError):
        service.reorder_categories(group_id, user_id, [uuid4()])

    session.commit.assert_not_called()


def test_used_chore_category_cannot_be_deleted() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    category = make_chore_category(group_id=group_id)
    session.scalar.side_effect = [group_id, category, 1]
    session.get.return_value = make_membership(group_id, user_id, role=GroupRole.MEMBER)
    session.scalars.return_value.all.return_value = [group_id]
    service, _ = make_service(session)

    with pytest.raises(ChoreCategoryInUseError):
        service.delete_category(category.id, user_id)

    session.delete.assert_not_called()


def test_list_tasks_returns_latest_completion_and_calculates_due_at() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    task = make_chore_task(interval_days=2)
    membership = make_membership(task.group_id, user_id, role=GroupRole.MEMBER)
    completion = make_completion(task.id, user_id)
    session.get.return_value = membership
    completion_result = MagicMock(all=MagicMock(return_value=[completion]))
    session.scalars.side_effect = [
        MagicMock(all=MagicMock(return_value=[task])),
        completion_result,
    ]
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="family-member", is_active=True),
    }

    result = service.list_tasks(task.group_id, user_id)

    assert result[0].last_completion is not None
    assert result[0].last_completion.completed_by_username == "family-member"
    assert result[0].next_due_at == completion.completed_at + timedelta(days=2)
    assert result[0].current_user_role is GroupRole.MEMBER
    completion_statement = session.scalars.call_args_list[1].args[0]
    sql = str(completion_statement.compile(dialect=postgresql.dialect()))
    assert "DISTINCT ON (chore_completions.task_id)" in sql
    assert "chore_completions.completed_at DESC" in sql
    assert "chore_completions.id DESC" in sql


def test_create_task_requires_group_admin() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    category = make_chore_category(group_id=group_id)
    session.get.side_effect = [make_membership(group_id, user_id, role=GroupRole.MEMBER), category]
    session.scalars.return_value.all.return_value = [group_id]
    service, _ = make_service(session)

    with pytest.raises(ChoreForbiddenError):
        service.create_task(group_id, user_id, "お風呂", 1, category.id)

    session.add.assert_not_called()


def test_create_task_persists_for_group_admin() -> None:
    session = MagicMock(spec=Session)
    group_id = uuid4()
    user_id = uuid4()
    category = make_chore_category(group_id=group_id)
    session.get.side_effect = [make_membership(group_id, user_id, role=GroupRole.ADMIN), category]
    session.scalars.return_value.all.return_value = [group_id]
    session.scalar.return_value = None
    service, _ = make_service(session)

    result = service.create_task(group_id, user_id, "お風呂", 1, category.id)

    task = session.add.call_args.args[0]
    assert isinstance(task, ChoreTask)
    assert task.group_id == group_id
    assert task.category_id == category.id
    assert result.category_id == category.id
    assert result.next_due_at == task.created_at + timedelta(days=1)
    session.commit.assert_called_once_with()


def test_complete_task_records_actor_and_resets_due_at() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    task = make_chore_task(interval_days=3)
    category = make_chore_category(category_id=task.category_id, group_id=task.group_id)
    session.scalar.side_effect = [task.group_id, task]
    session.get.side_effect = [make_membership(task.group_id, user_id, role=GroupRole.MEMBER), category]
    lock_result = MagicMock(all=MagicMock(return_value=[task.group_id]))
    session.scalars.return_value = lock_result
    service, directory = make_service(session)
    directory.list_by_ids.return_value = {
        user_id: PublicUser(id=user_id, username="cleaner", is_active=True),
    }

    result = service.complete_task(task.id, user_id)

    completion = session.add.call_args.args[0]
    assert isinstance(completion, ChoreCompletion)
    assert completion.completed_by_user_id == user_id
    assert completion.task_name_snapshot == task.name
    assert completion.category_id == category.id
    assert completion.category_name_snapshot == category.name
    assert result.last_completion is not None
    assert result.next_due_at == completion.completed_at + timedelta(days=3)


def test_complete_task_rejects_inactive_task() -> None:
    session = MagicMock(spec=Session)
    user_id = uuid4()
    task = make_chore_task(is_active=False)
    session.scalar.side_effect = [task.group_id, task]
    session.get.return_value = make_membership(task.group_id, user_id)
    session.scalars.return_value.all.return_value = [task.group_id]
    service, _ = make_service(session)

    with pytest.raises(ChoreInactiveTaskError):
        service.complete_task(task.id, user_id)

    session.add.assert_not_called()


def test_non_member_cannot_discover_task() -> None:
    session = MagicMock(spec=Session)
    task = make_chore_task()
    session.get.side_effect = [task, None]
    service, _ = make_service(session)

    with pytest.raises(ChoreNotFoundError):
        service.get_task(task.id, uuid4())
