from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.features.auth.public import User
from app.features.cleaning.models import CleaningCompletion, CleaningTask
from app.features.groups.public import FamilyGroup, FamilyGroupMember


class CleaningReportNotFoundError(Exception):
    pass


class CleaningReportInvalidMonthError(Exception):
    pass


class CleaningReportInvalidTimezoneError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CleaningMonthlySummary:
    completion_count: int
    unique_task_count: int
    participant_count: int
    category_count: int


@dataclass(frozen=True, slots=True)
class CleaningMonthlyDaily:
    day: date
    completion_count: int
    unique_task_count: int


@dataclass(frozen=True, slots=True)
class CleaningMonthlyCategory:
    category_id: UUID | None
    name: str
    completion_count: int
    unique_task_count: int


@dataclass(frozen=True, slots=True)
class CleaningMonthlyMember:
    user_id: UUID
    username: str
    completion_count: int
    unique_task_count: int
    completion_ratio: float


@dataclass(frozen=True, slots=True)
class CleaningMonthlyTaskMember:
    user_id: UUID
    username: str
    completion_count: int


@dataclass(frozen=True, slots=True)
class CleaningMonthlyTask:
    task_id: UUID
    name: str
    category_id: UUID | None
    category_name: str
    completion_count: int
    participant_count: int
    members: list[CleaningMonthlyTaskMember]


@dataclass(frozen=True, slots=True)
class CleaningMonthlyReport:
    group_id: UUID
    month: str
    timezone: str
    summary: CleaningMonthlySummary
    daily: list[CleaningMonthlyDaily]
    categories: list[CleaningMonthlyCategory]
    members: list[CleaningMonthlyMember]
    tasks: list[CleaningMonthlyTask]


class CleaningReportService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def monthly(self, group_id: UUID, user_id: UUID, month: str) -> CleaningMonthlyReport:
        group = self._group_for_member(group_id, user_id)
        month_start = self._parse_month(month)
        try:
            timezone = ZoneInfo(group.timezone)
        except ZoneInfoNotFoundError as error:
            raise CleaningReportInvalidTimezoneError from error

        next_month = date(month_start.year + (month_start.month == 12), month_start.month % 12 + 1, 1)
        start_at = datetime.combine(month_start, time.min, tzinfo=timezone).astimezone(UTC)
        end_at = datetime.combine(next_month, time.min, tzinfo=timezone).astimezone(UTC)
        completion_scope = self._completion_scope(group_id, start_at, end_at)

        summary_row = self._session.execute(
            select(
                func.count(completion_scope.c.completion_id),
                func.count(func.distinct(completion_scope.c.task_id)),
                func.count(func.distinct(completion_scope.c.completed_by_user_id)),
                func.count(func.distinct(completion_scope.c.category_key)),
            )
        ).one()
        daily = self._daily_stats(completion_scope, month_start, next_month, timezone)
        categories = self._category_stats(completion_scope)
        members = self._member_stats(completion_scope, int(summary_row[0] or 0))
        tasks = self._task_stats(completion_scope)

        return CleaningMonthlyReport(
            group_id=group_id,
            month=month,
            timezone=group.timezone,
            summary=CleaningMonthlySummary(
                completion_count=int(summary_row[0] or 0),
                unique_task_count=int(summary_row[1] or 0),
                participant_count=int(summary_row[2] or 0),
                category_count=int(summary_row[3] or 0),
            ),
            daily=daily,
            categories=categories,
            members=members,
            tasks=tasks,
        )

    def _group_for_member(self, group_id: UUID, user_id: UUID) -> FamilyGroup:
        group = self._session.scalar(
            select(FamilyGroup)
            .join(FamilyGroupMember, FamilyGroupMember.group_id == FamilyGroup.id)
            .where(FamilyGroup.id == group_id, FamilyGroupMember.user_id == user_id)
        )
        if group is None:
            raise CleaningReportNotFoundError
        return group

    @staticmethod
    def _parse_month(month: str) -> date:
        try:
            parsed = datetime.strptime(month, "%Y-%m").date()
        except ValueError as error:
            raise CleaningReportInvalidMonthError from error
        if parsed.strftime("%Y-%m") != month:
            raise CleaningReportInvalidMonthError
        return parsed

    @staticmethod
    def _completion_scope(group_id: UUID, start_at: datetime, end_at: datetime):
        category_key = func.coalesce(
            cast(CleaningCompletion.category_id, String),
            func.concat("name:", CleaningCompletion.category_name_snapshot),
        )
        return (
            select(
                CleaningCompletion.id.label("completion_id"),
                CleaningCompletion.task_id,
                CleaningCompletion.task_name_snapshot,
                CleaningCompletion.category_id,
                CleaningCompletion.category_name_snapshot,
                CleaningCompletion.completed_by_user_id,
                CleaningCompletion.completed_at,
                category_key.label("category_key"),
            )
            .join(CleaningTask, CleaningTask.id == CleaningCompletion.task_id)
            .where(
                CleaningTask.group_id == group_id,
                CleaningCompletion.completed_at >= start_at,
                CleaningCompletion.completed_at < end_at,
            )
            .subquery("monthly_cleaning_completions")
        )

    def _daily_stats(
        self,
        scope,
        month_start: date,
        next_month: date,
        timezone: ZoneInfo,
    ) -> list[CleaningMonthlyDaily]:
        local_day = func.date(func.timezone(str(timezone), scope.c.completed_at))
        rows = self._session.execute(
            select(
                local_day.label("day"),
                func.count(scope.c.completion_id).label("completion_count"),
                func.count(func.distinct(scope.c.task_id)).label("unique_task_count"),
            )
            .group_by(local_day)
            .order_by(local_day.asc())
        ).all()
        values = {
            row.day: CleaningMonthlyDaily(
                day=row.day,
                completion_count=int(row.completion_count),
                unique_task_count=int(row.unique_task_count),
            )
            for row in rows
        }
        return [
            values.get(day, CleaningMonthlyDaily(day=day, completion_count=0, unique_task_count=0))
            for day in self._days(month_start, next_month)
        ]

    def _category_stats(self, scope) -> list[CleaningMonthlyCategory]:
        counts = (
            select(
                scope.c.category_key,
                func.count(scope.c.completion_id).label("completion_count"),
                func.count(func.distinct(scope.c.task_id)).label("unique_task_count"),
            )
            .group_by(scope.c.category_key)
            .subquery("monthly_cleaning_category_counts")
        )
        labels = (
            select(
                scope.c.category_key,
                scope.c.category_id,
                scope.c.category_name_snapshot,
            )
            .distinct(scope.c.category_key)
            .order_by(scope.c.category_key, scope.c.completed_at.desc(), scope.c.completion_id.desc())
            .subquery("monthly_cleaning_category_labels")
        )
        rows = self._session.execute(
            select(
                labels.c.category_id,
                labels.c.category_name_snapshot,
                counts.c.completion_count,
                counts.c.unique_task_count,
            )
            .join(counts, counts.c.category_key == labels.c.category_key)
            .order_by(counts.c.completion_count.desc(), labels.c.category_name_snapshot.asc())
        ).all()
        return [
            CleaningMonthlyCategory(
                category_id=row.category_id,
                name=row.category_name_snapshot,
                completion_count=int(row.completion_count),
                unique_task_count=int(row.unique_task_count),
            )
            for row in rows
        ]

    def _member_stats(self, scope, total_completions: int) -> list[CleaningMonthlyMember]:
        rows = self._session.execute(
            select(
                scope.c.completed_by_user_id,
                User.username,
                func.count(scope.c.completion_id).label("completion_count"),
                func.count(func.distinct(scope.c.task_id)).label("unique_task_count"),
            )
            .join(User, User.id == scope.c.completed_by_user_id)
            .group_by(scope.c.completed_by_user_id, User.username)
            .order_by(func.count(scope.c.completion_id).desc(), User.username.asc())
        ).all()
        return [
            CleaningMonthlyMember(
                user_id=row.completed_by_user_id,
                username=row.username,
                completion_count=int(row.completion_count),
                unique_task_count=int(row.unique_task_count),
                completion_ratio=(int(row.completion_count) / total_completions if total_completions else 0),
            )
            for row in rows
        ]

    def _task_stats(self, scope) -> list[CleaningMonthlyTask]:
        counts = (
            select(
                scope.c.task_id,
                func.count(scope.c.completion_id).label("completion_count"),
                func.count(func.distinct(scope.c.completed_by_user_id)).label("participant_count"),
            )
            .group_by(scope.c.task_id)
            .subquery("monthly_cleaning_task_counts")
        )
        labels = (
            select(
                scope.c.task_id,
                scope.c.task_name_snapshot,
                scope.c.category_id,
                scope.c.category_name_snapshot,
            )
            .distinct(scope.c.task_id)
            .order_by(scope.c.task_id, scope.c.completed_at.desc(), scope.c.completion_id.desc())
            .subquery("monthly_cleaning_task_labels")
        )
        task_rows = self._session.execute(
            select(
                labels.c.task_id,
                labels.c.task_name_snapshot,
                labels.c.category_id,
                labels.c.category_name_snapshot,
                counts.c.completion_count,
                counts.c.participant_count,
            )
            .join(counts, counts.c.task_id == labels.c.task_id)
            .order_by(counts.c.completion_count.desc(), labels.c.task_name_snapshot.asc())
        ).all()
        member_rows = self._session.execute(
            select(
                scope.c.task_id,
                scope.c.completed_by_user_id,
                User.username,
                func.count(scope.c.completion_id).label("completion_count"),
            )
            .join(User, User.id == scope.c.completed_by_user_id)
            .group_by(scope.c.task_id, scope.c.completed_by_user_id, User.username)
            .order_by(scope.c.task_id, func.count(scope.c.completion_id).desc(), User.username.asc())
        ).all()
        members_by_task: dict[UUID, list[CleaningMonthlyTaskMember]] = defaultdict(list)
        for row in member_rows:
            members_by_task[row.task_id].append(
                CleaningMonthlyTaskMember(
                    user_id=row.completed_by_user_id,
                    username=row.username,
                    completion_count=int(row.completion_count),
                )
            )
        return [
            CleaningMonthlyTask(
                task_id=row.task_id,
                name=row.task_name_snapshot,
                category_id=row.category_id,
                category_name=row.category_name_snapshot,
                completion_count=int(row.completion_count),
                participant_count=int(row.participant_count),
                members=members_by_task[row.task_id],
            )
            for row in task_rows
        ]

    @staticmethod
    def _days(start: date, end: date) -> list[date]:
        return [date.fromordinal(value) for value in range(start.toordinal(), end.toordinal())]
