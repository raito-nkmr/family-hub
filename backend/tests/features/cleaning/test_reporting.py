from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.cleaning.reporting import (
    CleaningReportInvalidMonthError,
    CleaningReportNotFoundError,
    CleaningReportService,
)
from tests.features.groups.factories import make_group


def make_execute_result(*, one=None, all_rows=None) -> MagicMock:
    result = MagicMock()
    result.one.return_value = one
    result.all.return_value = all_rows or []
    return result


def test_monthly_report_aggregates_daily_category_member_and_task_stats() -> None:
    session = MagicMock(spec=Session)
    group = make_group()
    user_id = uuid4()
    task_id = uuid4()
    category_id = uuid4()
    session.scalar.return_value = group
    session.execute.side_effect = [
        make_execute_result(one=(4, 2, 2, 1)),
        make_execute_result(
            all_rows=[
                SimpleNamespace(day=date(2026, 8, 1), completion_count=3, unique_task_count=2),
            ]
        ),
        make_execute_result(
            all_rows=[
                SimpleNamespace(
                    category_id=category_id,
                    category_name_snapshot="掃除",
                    completion_count=4,
                    unique_task_count=2,
                ),
            ]
        ),
        make_execute_result(
            all_rows=[
                SimpleNamespace(
                    completed_by_user_id=user_id,
                    username="owner",
                    completion_count=4,
                    unique_task_count=2,
                ),
            ]
        ),
        make_execute_result(
            all_rows=[
                SimpleNamespace(
                    task_id=task_id,
                    task_name_snapshot="お風呂",
                    category_id=category_id,
                    category_name_snapshot="掃除",
                    completion_count=4,
                    participant_count=1,
                ),
            ]
        ),
        make_execute_result(
            all_rows=[
                SimpleNamespace(
                    task_id=task_id,
                    completed_by_user_id=user_id,
                    username="owner",
                    completion_count=4,
                ),
            ]
        ),
    ]

    report = CleaningReportService(session).monthly(group.id, user_id, "2026-08")

    assert report.timezone == "Asia/Tokyo"
    assert report.summary.completion_count == 4
    assert report.summary.unique_task_count == 2
    assert report.summary.participant_count == 2
    assert report.summary.category_count == 1
    assert len(report.daily) == 31
    assert report.daily[0].completion_count == 3
    assert report.daily[1].completion_count == 0
    assert report.categories[0].name == "掃除"
    assert report.members[0].completion_ratio == 1
    assert report.tasks[0].members[0].completion_count == 4

    summary_statement = session.execute.call_args_list[0].args[0]
    params = summary_statement.compile(dialect=postgresql.dialect()).params
    assert datetime(2026, 7, 31, 15, tzinfo=UTC) in params.values()
    assert datetime(2026, 8, 31, 15, tzinfo=UTC) in params.values()


def test_monthly_report_rejects_invalid_month() -> None:
    session = MagicMock(spec=Session)
    group = make_group()
    session.scalar.return_value = group

    with pytest.raises(CleaningReportInvalidMonthError):
        CleaningReportService(session).monthly(group.id, uuid4(), "2026-13")

    session.execute.assert_not_called()


def test_monthly_report_hides_non_members() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(CleaningReportNotFoundError):
        CleaningReportService(session).monthly(uuid4(), uuid4(), "2026-08")
