from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.cleaning.dependencies import get_cleaning_report_service, get_cleaning_service
from app.features.cleaning.reporting import (
    CleaningMonthlyReport,
    CleaningReportInvalidMonthError,
    CleaningReportInvalidTimezoneError,
    CleaningReportNotFoundError,
    CleaningReportService,
)
from app.features.cleaning.schemas import (
    CleaningCategoryCreate,
    CleaningCategoryListResponse,
    CleaningCategoryResponse,
    CleaningCategoryUpdate,
    CleaningMonthlyCategoryResponse,
    CleaningMonthlyDailyResponse,
    CleaningMonthlyMemberResponse,
    CleaningMonthlyReportResponse,
    CleaningMonthlySummaryResponse,
    CleaningMonthlyTaskMemberResponse,
    CleaningMonthlyTaskResponse,
    CleaningTaskCreate,
    CleaningTaskListResponse,
    CleaningTaskResponse,
    CleaningTaskUpdate,
)
from app.features.cleaning.service import (
    CleaningCategoryDuplicateError,
    CleaningCategoryInUseError,
    CleaningCategoryNotFoundError,
    CleaningCategorySummary,
    CleaningForbiddenError,
    CleaningInactiveTaskError,
    CleaningNotFoundError,
    CleaningPersistenceError,
    CleaningService,
    CleaningTaskSummary,
)

router = APIRouter(
    tags=["cleaning"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)


def _response(task: CleaningTaskSummary) -> CleaningTaskResponse:
    return CleaningTaskResponse.model_validate(task)


def _category_response(category: CleaningCategorySummary) -> CleaningCategoryResponse:
    return CleaningCategoryResponse.model_validate(category)


def _report_response(report: CleaningMonthlyReport) -> CleaningMonthlyReportResponse:
    return CleaningMonthlyReportResponse(
        group_id=report.group_id,
        month=report.month,
        timezone=report.timezone,
        summary=CleaningMonthlySummaryResponse(
            completion_count=report.summary.completion_count,
            unique_task_count=report.summary.unique_task_count,
            participant_count=report.summary.participant_count,
            category_count=report.summary.category_count,
        ),
        daily=[
            CleaningMonthlyDailyResponse(
                day=item.day,
                completion_count=item.completion_count,
                unique_task_count=item.unique_task_count,
            )
            for item in report.daily
        ],
        categories=[
            CleaningMonthlyCategoryResponse(
                category_id=item.category_id,
                name=item.name,
                completion_count=item.completion_count,
                unique_task_count=item.unique_task_count,
            )
            for item in report.categories
        ],
        members=[
            CleaningMonthlyMemberResponse(
                user_id=item.user_id,
                username=item.username,
                completion_count=item.completion_count,
                unique_task_count=item.unique_task_count,
                completion_ratio=item.completion_ratio,
            )
            for item in report.members
        ],
        tasks=[
            CleaningMonthlyTaskResponse(
                task_id=item.task_id,
                name=item.name,
                category_id=item.category_id,
                category_name=item.category_name,
                completion_count=item.completion_count,
                participant_count=item.participant_count,
                members=[
                    CleaningMonthlyTaskMemberResponse(
                        user_id=member.user_id,
                        username=member.username,
                        completion_count=member.completion_count,
                    )
                    for member in item.members
                ],
            )
            for item in report.tasks
        ],
    )


def _raise_cleaning_error(error: Exception) -> NoReturn:
    if isinstance(error, CleaningNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cleaning task not found") from error
    if isinstance(error, CleaningForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group administrator required") from error
    if isinstance(error, CleaningInactiveTaskError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cleaning task is inactive") from error
    if isinstance(error, CleaningPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update cleaning task",
        ) from error
    if isinstance(error, CleaningCategoryNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cleaning category not found") from error
    if isinstance(error, CleaningCategoryDuplicateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cleaning category already exists") from error
    if isinstance(error, CleaningCategoryInUseError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cleaning category is in use") from error
    if isinstance(error, CleaningReportNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cleaning report not found") from error
    if isinstance(error, CleaningReportInvalidMonthError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid report month") from error
    if isinstance(error, CleaningReportInvalidTimezoneError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not determine the group timezone",
        ) from error
    raise error


@router.get("/groups/{group_id}/tasks", response_model=CleaningTaskListResponse)
def list_cleaning_tasks(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningTaskListResponse:
    try:
        return CleaningTaskListResponse(
            items=[_response(task) for task in service.list_tasks(group_id, authenticated_user.id)]
        )
    except CleaningNotFoundError as error:
        _raise_cleaning_error(error)


@router.get("/groups/{group_id}/categories", response_model=CleaningCategoryListResponse)
def list_cleaning_categories(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningCategoryListResponse:
    try:
        return CleaningCategoryListResponse(
            items=[
                _category_response(category) for category in service.list_categories(group_id, authenticated_user.id)
            ]
        )
    except (CleaningCategoryNotFoundError, CleaningNotFoundError) as error:
        _raise_cleaning_error(error)


@router.get("/groups/{group_id}/reports/monthly", response_model=CleaningMonthlyReportResponse)
def get_cleaning_monthly_report(
    group_id: UUID,
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningReportService, Depends(get_cleaning_report_service)],
) -> CleaningMonthlyReportResponse:
    try:
        return _report_response(service.monthly(group_id, authenticated_user.id, month))
    except (
        CleaningReportInvalidMonthError,
        CleaningReportInvalidTimezoneError,
        CleaningReportNotFoundError,
    ) as error:
        _raise_cleaning_error(error)


@router.post(
    "/groups/{group_id}/categories",
    response_model=CleaningCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_cleaning_category(
    group_id: UUID,
    body: CleaningCategoryCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningCategoryResponse:
    try:
        return _category_response(service.create_category(group_id, authenticated_user.id, body.name))
    except (
        CleaningCategoryDuplicateError,
        CleaningCategoryNotFoundError,
        CleaningNotFoundError,
        CleaningPersistenceError,
    ) as error:
        _raise_cleaning_error(error)


@router.patch(
    "/categories/{category_id}",
    response_model=CleaningCategoryResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_cleaning_category(
    category_id: UUID,
    body: CleaningCategoryUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningCategoryResponse:
    try:
        return _category_response(service.update_category(category_id, authenticated_user.id, body.name))
    except (
        CleaningCategoryDuplicateError,
        CleaningCategoryNotFoundError,
        CleaningNotFoundError,
        CleaningPersistenceError,
    ) as error:
        _raise_cleaning_error(error)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_cleaning_category(
    category_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> Response:
    try:
        service.delete_category(category_id, authenticated_user.id)
    except (
        CleaningCategoryInUseError,
        CleaningCategoryNotFoundError,
        CleaningNotFoundError,
        CleaningPersistenceError,
    ) as error:
        _raise_cleaning_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/groups/{group_id}/tasks",
    response_model=CleaningTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_cleaning_task(
    group_id: UUID,
    body: CleaningTaskCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningTaskResponse:
    try:
        return _response(
            service.create_task(
                group_id,
                authenticated_user.id,
                body.name,
                body.interval_days,
                body.category_id,
            )
        )
    except (
        CleaningCategoryNotFoundError,
        CleaningForbiddenError,
        CleaningNotFoundError,
        CleaningPersistenceError,
    ) as error:
        _raise_cleaning_error(error)


@router.get("/tasks/{task_id}", response_model=CleaningTaskResponse)
def get_cleaning_task(
    task_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningTaskResponse:
    try:
        return _response(service.get_task(task_id, authenticated_user.id))
    except CleaningNotFoundError as error:
        _raise_cleaning_error(error)


@router.patch(
    "/tasks/{task_id}",
    response_model=CleaningTaskResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_cleaning_task(
    task_id: UUID,
    body: CleaningTaskUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningTaskResponse:
    try:
        return _response(
            service.update_task(
                task_id,
                authenticated_user.id,
                name=body.name,
                category_id=body.category_id,
                interval_days=body.interval_days,
                is_active=body.is_active,
            )
        )
    except (
        CleaningCategoryNotFoundError,
        CleaningForbiddenError,
        CleaningNotFoundError,
        CleaningPersistenceError,
    ) as error:
        _raise_cleaning_error(error)


@router.post(
    "/tasks/{task_id}/completions",
    response_model=CleaningTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def complete_cleaning_task(
    task_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[CleaningService, Depends(get_cleaning_service)],
) -> CleaningTaskResponse:
    try:
        return _response(service.complete_task(task_id, authenticated_user.id))
    except (CleaningNotFoundError, CleaningInactiveTaskError, CleaningPersistenceError) as error:
        _raise_cleaning_error(error)
