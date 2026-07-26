from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.auth.public import UserDirectory
from app.features.cleaning.models import CleaningCompletion, CleaningTask
from app.features.groups.public import FamilyGroupMember, GroupRole, lock_user_group_ids


class CleaningNotFoundError(Exception):
    pass


class CleaningForbiddenError(Exception):
    pass


class CleaningInactiveTaskError(Exception):
    pass


class CleaningPersistenceError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CleaningCompletionSummary:
    id: UUID
    completed_by_user_id: UUID
    completed_by_username: str
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class CleaningTaskSummary:
    id: UUID
    group_id: UUID
    name: str
    interval_days: int
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    next_due_at: datetime
    current_user_role: GroupRole
    last_completion: CleaningCompletionSummary | None


class CleaningService:
    def __init__(self, session: Session, user_directory: UserDirectory) -> None:
        self._session = session
        self._user_directory = user_directory

    def list_tasks(self, group_id: UUID, user_id: UUID) -> list[CleaningTaskSummary]:
        membership = self._require_membership(group_id, user_id)
        tasks = list(
            self._session.scalars(
                select(CleaningTask)
                .where(CleaningTask.group_id == group_id)
                .order_by(CleaningTask.is_active.desc(), CleaningTask.created_at.asc(), CleaningTask.id.asc())
            ).all()
        )
        completions = self._latest_completions({task.id for task in tasks})
        summaries = [self._summary(task, membership, completions.get(task.id)) for task in tasks]
        return sorted(summaries, key=lambda task: (not task.is_active, task.next_due_at, task.name, str(task.id)))

    def get_task(self, task_id: UUID, user_id: UUID) -> CleaningTaskSummary:
        task = self._session.get(CleaningTask, task_id)
        if task is None:
            raise CleaningNotFoundError
        membership = self._require_membership(task.group_id, user_id)
        completion = self._latest_completions({task.id}).get(task.id)
        return self._summary(task, membership, completion)

    def create_task(self, group_id: UUID, user_id: UUID, name: str, interval_days: int) -> CleaningTaskSummary:
        membership = self._lock_admin(group_id, user_id)
        now = datetime.now(UTC)
        task = CleaningTask(
            id=uuid4(),
            group_id=group_id,
            name=name,
            interval_days=interval_days,
            is_active=True,
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(task)
        self._commit("Could not create cleaning task")
        return self._summary(task, membership, None)

    def update_task(
        self,
        task_id: UUID,
        user_id: UUID,
        *,
        name: str | None,
        interval_days: int | None,
        is_active: bool | None,
    ) -> CleaningTaskSummary:
        group_id = self._task_group_id(task_id)
        membership = self._lock_admin(group_id, user_id)
        task = self._locked_task(task_id)
        if task.group_id != group_id:
            raise CleaningNotFoundError
        if name is not None:
            task.name = name
        if interval_days is not None:
            task.interval_days = interval_days
        if is_active is not None:
            task.is_active = is_active
        task.updated_at = datetime.now(UTC)
        self._commit("Could not update cleaning task")
        completion = self._latest_completions({task.id}).get(task.id)
        return self._summary(task, membership, completion)

    def complete_task(self, task_id: UUID, user_id: UUID) -> CleaningTaskSummary:
        group_id = self._task_group_id(task_id)
        membership = self._lock_membership(group_id, user_id)
        task = self._locked_task(task_id)
        if task.group_id != group_id:
            raise CleaningNotFoundError
        if not task.is_active:
            raise CleaningInactiveTaskError
        completion = CleaningCompletion(
            id=uuid4(),
            task_id=task.id,
            completed_by_user_id=user_id,
            completed_at=datetime.now(UTC),
        )
        self._session.add(completion)
        self._commit("Could not complete cleaning task")
        username = self._user_directory.list_by_ids({user_id})[user_id].username
        return self._summary(
            task,
            membership,
            CleaningCompletionSummary(
                id=completion.id,
                completed_by_user_id=user_id,
                completed_by_username=username,
                completed_at=completion.completed_at,
            ),
        )

    def _locked_task(self, task_id: UUID) -> CleaningTask:
        task = self._session.scalar(select(CleaningTask).where(CleaningTask.id == task_id).with_for_update())
        if task is None:
            raise CleaningNotFoundError
        return task

    def _task_group_id(self, task_id: UUID) -> UUID:
        group_id = self._session.scalar(select(CleaningTask.group_id).where(CleaningTask.id == task_id))
        if group_id is None:
            raise CleaningNotFoundError
        return group_id

    def _require_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._session.get(FamilyGroupMember, (group_id, user_id))
        if membership is None:
            raise CleaningNotFoundError
        return membership

    def _require_admin(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._require_membership(group_id, user_id)
        if GroupRole(membership.role) is not GroupRole.ADMIN:
            raise CleaningForbiddenError
        return membership

    def _lock_membership(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        if group_id not in lock_user_group_ids(self._session, user_id, {group_id}):
            raise CleaningNotFoundError
        return self._require_membership(group_id, user_id)

    def _lock_admin(self, group_id: UUID, user_id: UUID) -> FamilyGroupMember:
        membership = self._lock_membership(group_id, user_id)
        if GroupRole(membership.role) is not GroupRole.ADMIN:
            raise CleaningForbiddenError
        return membership

    def _latest_completions(self, task_ids: set[UUID]) -> dict[UUID, CleaningCompletionSummary]:
        if not task_ids:
            return {}
        latest_rows = {
            completion.task_id: completion
            for completion in self._session.scalars(
                select(CleaningCompletion)
                .distinct(CleaningCompletion.task_id)
                .where(CleaningCompletion.task_id.in_(task_ids))
                .order_by(
                    CleaningCompletion.task_id.asc(),
                    CleaningCompletion.completed_at.desc(),
                    CleaningCompletion.id.desc(),
                )
            ).all()
        }
        users = self._user_directory.list_by_ids(
            {completion.completed_by_user_id for completion in latest_rows.values()}
        )
        return {
            task_id: CleaningCompletionSummary(
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
        task: CleaningTask,
        membership: FamilyGroupMember,
        completion: CleaningCompletionSummary | None,
    ) -> CleaningTaskSummary:
        baseline = completion.completed_at if completion is not None else task.created_at
        return CleaningTaskSummary(
            id=task.id,
            group_id=task.group_id,
            name=task.name,
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
            raise CleaningPersistenceError(message) from error
