from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.auth.public import UserDirectory
from app.features.chores.models import ChoreCategory, ChoreCompletion, ChoreTask
from app.features.groups.public import FamilyGroupMember, GroupRole, lock_user_group_ids


class ChoreNotFoundError(Exception):
    pass


class ChoreForbiddenError(Exception):
    pass


class ChoreInactiveTaskError(Exception):
    pass


class ChorePersistenceError(Exception):
    pass


class ChoreCategoryNotFoundError(Exception):
    pass


class ChoreCategoryDuplicateError(Exception):
    pass


class ChoreCategoryInUseError(Exception):
    pass


class ChoreCategoryOrderInvalidError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ChoreCategorySummary:
    id: UUID
    group_id: UUID
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChoreCompletionSummary:
    id: UUID
    completed_by_user_id: UUID
    completed_by_username: str
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class ChoreTaskSummary:
    id: UUID
    group_id: UUID
    name: str
    category_id: UUID
    interval_days: int
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    next_due_at: datetime
    current_user_role: GroupRole
    last_completion: ChoreCompletionSummary | None


class ChoreService:
    def __init__(self, session: Session, user_directory: UserDirectory) -> None:
        self._session = session
        self._user_directory = user_directory

    def list_categories(self, group_id: UUID, user_id: UUID) -> list[ChoreCategorySummary]:
        self._require_membership(group_id, user_id)
        categories = self._session.scalars(
            select(ChoreCategory)
            .where(ChoreCategory.group_id == group_id)
            .order_by(ChoreCategory.sort_order, func.lower(ChoreCategory.name), ChoreCategory.id)
        ).all()
        return [self._category_summary(category) for category in categories]

    def create_category(self, group_id: UUID, user_id: UUID, name: str) -> ChoreCategorySummary:
        self._lock_membership(group_id, user_id)
        normalized_name = name.strip()
        if self._category_exists(group_id, normalized_name):
            raise ChoreCategoryDuplicateError
        last_sort_order = self._session.scalar(
            select(func.max(ChoreCategory.sort_order)).where(ChoreCategory.group_id == group_id)
        )
        now = datetime.now(UTC)
        category = ChoreCategory(
            id=uuid4(),
            group_id=group_id,
            name=normalized_name,
            sort_order=int(last_sort_order if last_sort_order is not None else -1) + 1,
            created_at=now,
            updated_at=now,
        )
        self._session.add(category)
        self._commit_category("Could not create chore category")
        return self._category_summary(category)

    def update_category(self, category_id: UUID, user_id: UUID, name: str) -> ChoreCategorySummary:
        group_id = self._category_group_id(category_id)
        self._lock_membership(group_id, user_id)
        category = self._locked_category(category_id)
        if category.group_id != group_id:
            raise ChoreCategoryNotFoundError
        normalized_name = name.strip()
        if self._category_exists(group_id, normalized_name, exclude_id=category_id):
            raise ChoreCategoryDuplicateError
        category.name = normalized_name
        category.updated_at = datetime.now(UTC)
        self._commit_category("Could not update chore category")
        return self._category_summary(category)

    def reorder_categories(
        self,
        group_id: UUID,
        user_id: UUID,
        category_ids: list[UUID],
    ) -> list[ChoreCategorySummary]:
        self._lock_membership(group_id, user_id)
        categories = list(
            self._session.scalars(
                select(ChoreCategory)
                .where(ChoreCategory.group_id == group_id)
                .order_by(ChoreCategory.sort_order, func.lower(ChoreCategory.name), ChoreCategory.id)
                .with_for_update()
            ).all()
        )
        category_by_id = {category.id: category for category in categories}
        if len(category_ids) != len(categories) or len(set(category_ids)) != len(category_ids):
            raise ChoreCategoryOrderInvalidError
        if set(category_ids) != set(category_by_id):
            raise ChoreCategoryOrderInvalidError
        now = datetime.now(UTC)
        for sort_order, category_id in enumerate(category_ids):
            category = category_by_id[category_id]
            category.sort_order = sort_order
            category.updated_at = now
        self._commit_category("Could not reorder chore categories")
        return [self._category_summary(category_by_id[category_id]) for category_id in category_ids]

    def delete_category(self, category_id: UUID, user_id: UUID) -> None:
        group_id = self._category_group_id(category_id)
        self._lock_membership(group_id, user_id)
        category = self._locked_category(category_id)
        if category.group_id != group_id:
            raise ChoreCategoryNotFoundError
        task_count = self._session.scalar(
            select(func.count()).select_from(ChoreTask).where(ChoreTask.category_id == category_id)
        )
        if task_count:
            raise ChoreCategoryInUseError
        self._session.delete(category)
        self._commit("Could not delete chore category")

    def list_tasks(self, group_id: UUID, user_id: UUID) -> list[ChoreTaskSummary]:
        membership = self._require_membership(group_id, user_id)
        tasks = list(
            self._session.scalars(
                select(ChoreTask)
                .where(ChoreTask.group_id == group_id)
                .order_by(ChoreTask.is_active.desc(), ChoreTask.created_at.asc(), ChoreTask.id.asc())
            ).all()
        )
        completions = self._latest_completions({task.id for task in tasks})
        summaries = [self._summary(task, membership, completions.get(task.id)) for task in tasks]
        return sorted(summaries, key=lambda task: (not task.is_active, task.next_due_at, task.name, str(task.id)))

    def get_task(self, task_id: UUID, user_id: UUID) -> ChoreTaskSummary:
        task = self._session.get(ChoreTask, task_id)
        if task is None:
            raise ChoreNotFoundError
        membership = self._require_membership(task.group_id, user_id)
        completion = self._latest_completions({task.id}).get(task.id)
        return self._summary(task, membership, completion)

    def create_task(
        self,
        group_id: UUID,
        user_id: UUID,
        name: str,
        interval_days: int,
        category_id: UUID,
    ) -> ChoreTaskSummary:
        membership = self._lock_admin(group_id, user_id)
        self._require_category(category_id, group_id)
        now = datetime.now(UTC)
        task = ChoreTask(
            id=uuid4(),
            group_id=group_id,
            name=name,
            category_id=category_id,
            interval_days=interval_days,
            is_active=True,
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(task)
        self._commit("Could not create chore task")
        return self._summary(task, membership, None)

    def update_task(
        self,
        task_id: UUID,
        user_id: UUID,
        *,
        name: str | None,
        category_id: UUID | None,
        interval_days: int | None,
        is_active: bool | None,
    ) -> ChoreTaskSummary:
        group_id = self._task_group_id(task_id)
        membership = self._lock_admin(group_id, user_id)
        task = self._locked_task(task_id)
        if task.group_id != group_id:
            raise ChoreNotFoundError
        if category_id is not None:
            self._require_category(category_id, group_id)
        if name is not None:
            task.name = name
        if category_id is not None:
            task.category_id = category_id
        if interval_days is not None:
            task.interval_days = interval_days
        if is_active is not None:
            task.is_active = is_active
        task.updated_at = datetime.now(UTC)
        self._commit("Could not update chore task")
        completion = self._latest_completions({task.id}).get(task.id)
        return self._summary(task, membership, completion)

    def complete_task(self, task_id: UUID, user_id: UUID) -> ChoreTaskSummary:
        group_id = self._task_group_id(task_id)
        membership = self._lock_membership(group_id, user_id)
        task = self._locked_task(task_id)
        if task.group_id != group_id:
            raise ChoreNotFoundError
        if not task.is_active:
            raise ChoreInactiveTaskError
        category = self._require_category(task.category_id, task.group_id)
        completion = ChoreCompletion(
            id=uuid4(),
            task_id=task.id,
            task_name_snapshot=task.name,
            category_id=category.id,
            category_name_snapshot=category.name,
            completed_by_user_id=user_id,
            completed_at=datetime.now(UTC),
        )
        self._session.add(completion)
        self._commit("Could not complete chore task")
        username = self._user_directory.list_by_ids({user_id})[user_id].username
        return self._summary(
            task,
            membership,
            ChoreCompletionSummary(
                id=completion.id,
                completed_by_user_id=user_id,
                completed_by_username=username,
                completed_at=completion.completed_at,
            ),
        )

    def _locked_task(self, task_id: UUID) -> ChoreTask:
        task = self._session.scalar(select(ChoreTask).where(ChoreTask.id == task_id).with_for_update())
        if task is None:
            raise ChoreNotFoundError
        return task

    def _locked_category(self, category_id: UUID) -> ChoreCategory:
        category = self._session.scalar(select(ChoreCategory).where(ChoreCategory.id == category_id).with_for_update())
        if category is None:
            raise ChoreCategoryNotFoundError
        return category

    def _category_group_id(self, category_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ChoreCategory.group_id).where(ChoreCategory.id == category_id))
        if group_id is None:
            raise ChoreCategoryNotFoundError
        return group_id

    def _require_category(self, category_id: UUID, group_id: UUID) -> ChoreCategory:
        category = self._session.get(ChoreCategory, category_id)
        if category is None or category.group_id != group_id:
            raise ChoreCategoryNotFoundError
        return category

    def _category_exists(self, group_id: UUID, name: str, *, exclude_id: UUID | None = None) -> bool:
        statement = select(ChoreCategory.id).where(
            ChoreCategory.group_id == group_id,
            func.lower(ChoreCategory.name) == name.lower(),
        )
        if exclude_id is not None:
            statement = statement.where(ChoreCategory.id != exclude_id)
        return self._session.scalar(statement) is not None

    def _task_group_id(self, task_id: UUID) -> UUID:
        group_id = self._session.scalar(select(ChoreTask.group_id).where(ChoreTask.id == task_id))
        if group_id is None:
            raise ChoreNotFoundError
        return group_id

    def _require_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._session.get(FamilyGroupMember, (group_id, user_id))
        if membership is None:
            raise ChoreNotFoundError
        return membership

    def _require_admin(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._require_membership(group_id, user_id)
        if GroupRole(membership.role) is not GroupRole.ADMIN:
            raise ChoreForbiddenError
        return membership

    def _lock_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        if group_id not in lock_user_group_ids(self._session, user_id, {group_id}):
            raise ChoreNotFoundError
        return self._require_membership(group_id, user_id)

    def _lock_admin(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._lock_membership(group_id, user_id)
        if GroupRole(membership.role) is not GroupRole.ADMIN:
            raise ChoreForbiddenError
        return membership

    def _latest_completions(self, task_ids: set[UUID]) -> dict[UUID, ChoreCompletionSummary]:
        if not task_ids:
            return {}
        latest_rows = {
            completion.task_id: completion
            for completion in self._session.scalars(
                select(ChoreCompletion)
                .distinct(ChoreCompletion.task_id)
                .where(ChoreCompletion.task_id.in_(task_ids))
                .order_by(
                    ChoreCompletion.task_id.asc(),
                    ChoreCompletion.completed_at.desc(),
                    ChoreCompletion.id.desc(),
                )
            ).all()
        }
        users = self._user_directory.list_by_ids(
            {completion.completed_by_user_id for completion in latest_rows.values()}
        )
        return {
            task_id: ChoreCompletionSummary(
                id=completion.id,
                completed_by_user_id=completion.completed_by_user_id,
                completed_by_username=users[completion.completed_by_user_id].username,
                completed_at=completion.completed_at,
            )
            for task_id, completion in latest_rows.items()
            if completion.completed_by_user_id in users
        }

    @staticmethod
    def _summary(
        task: ChoreTask,
        membership: FamilyGroupMember,
        completion: ChoreCompletionSummary | None,
    ) -> ChoreTaskSummary:
        baseline = completion.completed_at if completion is not None else task.created_at
        return ChoreTaskSummary(
            id=task.id,
            group_id=task.group_id,
            name=task.name,
            category_id=task.category_id,
            interval_days=task.interval_days,
            is_active=task.is_active,
            created_by_user_id=task.created_by_user_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            next_due_at=baseline + timedelta(days=task.interval_days),
            current_user_role=GroupRole(membership.role),
            last_completion=completion,
        )

    def _commit(self, message: str) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise ChorePersistenceError(message) from error

    def _commit_category(self, message: str) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise ChorePersistenceError(message) from error

    @staticmethod
    def _category_summary(category: ChoreCategory) -> ChoreCategorySummary:
        return ChoreCategorySummary(
            id=category.id,
            group_id=category.group_id,
            name=category.name,
            sort_order=category.sort_order,
            created_at=category.created_at,
            updated_at=category.updated_at,
        )
