from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.chores.dependencies import get_chore_monthly_report_service, get_chore_service
from app.features.chores.reporting import (
    ChoreMonthlyReport,
    ChoreMonthlyReportInvalidMonthError,
    ChoreMonthlyReportInvalidTimezoneError,
    ChoreMonthlyReportNotFoundError,
    ChoreMonthlyReportService,
)
from app.features.chores.schemas import (
    ChoreCategoryCreate,
    ChoreCategoryListResponse,
    ChoreCategoryOrderUpdate,
    ChoreCategoryResponse,
    ChoreCategoryUpdate,
    ChoreMonthlyCategoryResponse,
    ChoreMonthlyDailyResponse,
    ChoreMonthlyMemberResponse,
    ChoreMonthlyReportResponse,
    ChoreMonthlySummaryResponse,
    ChoreMonthlyTaskMemberResponse,
    ChoreMonthlyTaskResponse,
    ChoreTaskCreate,
    ChoreTaskListResponse,
    ChoreTaskResponse,
    ChoreTaskUpdate,
)
from app.features.chores.service import (
    ChoreCategoryDuplicateError,
    ChoreCategoryInUseError,
    ChoreCategoryNotFoundError,
    ChoreCategoryOrderInvalidError,
    ChoreCategorySummary,
    ChoreForbiddenError,
    ChoreInactiveTaskError,
    ChoreNotFoundError,
    ChorePersistenceError,
    ChoreService,
    ChoreTaskSummary,
)

router = APIRouter(
    tags=["chores"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)


def _response(task: ChoreTaskSummary) -> ChoreTaskResponse:
    return ChoreTaskResponse.model_validate(task)


def _category_response(category: ChoreCategorySummary) -> ChoreCategoryResponse:
    return ChoreCategoryResponse.model_validate(category)


def _report_response(report: ChoreMonthlyReport) -> ChoreMonthlyReportResponse:
    return ChoreMonthlyReportResponse(
        group_id=report.group_id,
        month=report.month,
        timezone=report.timezone,
        summary=ChoreMonthlySummaryResponse(
            completion_count=report.summary.completion_count,
            unique_task_count=report.summary.unique_task_count,
            participant_count=report.summary.participant_count,
            category_count=report.summary.category_count,
        ),
        daily=[
            ChoreMonthlyDailyResponse(
                day=item.day,
                completion_count=item.completion_count,
                unique_task_count=item.unique_task_count,
            )
            for item in report.daily
        ],
        categories=[
            ChoreMonthlyCategoryResponse(
                category_id=item.category_id,
                name=item.name,
                completion_count=item.completion_count,
                unique_task_count=item.unique_task_count,
            )
            for item in report.categories
        ],
        members=[
            ChoreMonthlyMemberResponse(
                user_id=item.user_id,
                username=item.username,
                completion_count=item.completion_count,
                unique_task_count=item.unique_task_count,
                completion_ratio=item.completion_ratio,
            )
            for item in report.members
        ],
        tasks=[
            ChoreMonthlyTaskResponse(
                task_id=item.task_id,
                task_name=item.task_name,
                category_id=item.category_id,
                category_name=item.category_name,
                completion_count=item.completion_count,
                participant_count=item.participant_count,
                members=[
                    ChoreMonthlyTaskMemberResponse(
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


def _raise_chore_error(error: Exception) -> NoReturn:
    if isinstance(error, ChoreNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore task not found") from error
    if isinstance(error, ChoreForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Group administrator required") from error
    if isinstance(error, ChoreInactiveTaskError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chore task is inactive") from error
    if isinstance(error, ChorePersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update chore task",
        ) from error
    if isinstance(error, ChoreCategoryNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore category not found") from error
    if isinstance(error, ChoreCategoryDuplicateError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chore category already exists") from error
    if isinstance(error, ChoreCategoryInUseError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Chore category is in use") from error
    if isinstance(error, ChoreCategoryOrderInvalidError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid category order",
        ) from error
    if isinstance(error, ChoreMonthlyReportNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chore report not found") from error
    if isinstance(error, ChoreMonthlyReportInvalidMonthError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid report month") from error
    if isinstance(error, ChoreMonthlyReportInvalidTimezoneError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not determine the group timezone",
        ) from error
    raise error


@router.get("/groups/{group_id}/tasks", response_model=ChoreTaskListResponse)
def list_chore_tasks(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreTaskListResponse:
    try:
        return ChoreTaskListResponse(
            items=[_response(task) for task in service.list_tasks(group_id, authenticated_user.id)]
        )
    except ChoreNotFoundError as error:
        _raise_chore_error(error)


@router.get("/groups/{group_id}/categories", response_model=ChoreCategoryListResponse)
def list_chore_categories(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreCategoryListResponse:
    try:
        return ChoreCategoryListResponse(
            items=[
                _category_response(category) for category in service.list_categories(group_id, authenticated_user.id)
            ]
        )
    except (ChoreCategoryNotFoundError, ChoreNotFoundError) as error:
        _raise_chore_error(error)


@router.patch(
    "/groups/{group_id}/categories/order",
    response_model=ChoreCategoryListResponse,
    dependencies=[Depends(require_csrf_token)],
)
def reorder_chore_categories(
    group_id: UUID,
    body: ChoreCategoryOrderUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreCategoryListResponse:
    try:
        return ChoreCategoryListResponse(
            items=[
                _category_response(category)
                for category in service.reorder_categories(group_id, authenticated_user.id, body.category_ids)
            ]
        )
    except (
        ChoreCategoryOrderInvalidError,
        ChoreCategoryNotFoundError,
        ChoreNotFoundError,
    ) as error:
        _raise_chore_error(error)


@router.get("/groups/{group_id}/reports/monthly", response_model=ChoreMonthlyReportResponse)
def get_chore_monthly_report(
    group_id: UUID,
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreMonthlyReportService, Depends(get_chore_monthly_report_service)],
) -> ChoreMonthlyReportResponse:
    try:
        return _report_response(service.monthly(group_id, authenticated_user.id, month))
    except (
        ChoreMonthlyReportInvalidMonthError,
        ChoreMonthlyReportInvalidTimezoneError,
        ChoreMonthlyReportNotFoundError,
    ) as error:
        _raise_chore_error(error)


@router.post(
    "/groups/{group_id}/categories",
    response_model=ChoreCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_chore_category(
    group_id: UUID,
    body: ChoreCategoryCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreCategoryResponse:
    try:
        return _category_response(service.create_category(group_id, authenticated_user.id, body.name))
    except (
        ChoreCategoryDuplicateError,
        ChoreCategoryNotFoundError,
        ChoreNotFoundError,
        ChorePersistenceError,
    ) as error:
        _raise_chore_error(error)


@router.patch(
    "/categories/{category_id}",
    response_model=ChoreCategoryResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_chore_category(
    category_id: UUID,
    body: ChoreCategoryUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreCategoryResponse:
    try:
        return _category_response(service.update_category(category_id, authenticated_user.id, body.name))
    except (
        ChoreCategoryDuplicateError,
        ChoreCategoryNotFoundError,
        ChoreNotFoundError,
        ChorePersistenceError,
    ) as error:
        _raise_chore_error(error)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_chore_category(
    category_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> Response:
    try:
        service.delete_category(category_id, authenticated_user.id)
    except (
        ChoreCategoryInUseError,
        ChoreCategoryNotFoundError,
        ChoreNotFoundError,
        ChorePersistenceError,
    ) as error:
        _raise_chore_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/groups/{group_id}/tasks",
    response_model=ChoreTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_chore_task(
    group_id: UUID,
    body: ChoreTaskCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreTaskResponse:
    try:
        return _response(
            service.create_task(
                group_id,
                authenticated_user.id,
                body.task_name,
                body.interval_days,
                body.category_id,
            )
        )
    except (
        ChoreCategoryNotFoundError,
        ChoreForbiddenError,
        ChoreNotFoundError,
        ChorePersistenceError,
    ) as error:
        _raise_chore_error(error)


@router.get("/tasks/{task_id}", response_model=ChoreTaskResponse)
def get_chore_task(
    task_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreTaskResponse:
    try:
        return _response(service.get_task(task_id, authenticated_user.id))
    except ChoreNotFoundError as error:
        _raise_chore_error(error)


@router.patch(
    "/tasks/{task_id}",
    response_model=ChoreTaskResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_chore_task(
    task_id: UUID,
    body: ChoreTaskUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreTaskResponse:
    try:
        return _response(
            service.update_task(
                task_id,
                authenticated_user.id,
                task_name=body.task_name,
                category_id=body.category_id,
                interval_days=body.interval_days,
                is_active=body.is_active,
            )
        )
    except (
        ChoreCategoryNotFoundError,
        ChoreForbiddenError,
        ChoreNotFoundError,
        ChorePersistenceError,
    ) as error:
        _raise_chore_error(error)


@router.post(
    "/tasks/{task_id}/completions",
    response_model=ChoreTaskResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def complete_chore_task(
    task_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ChoreService, Depends(get_chore_service)],
) -> ChoreTaskResponse:
    try:
        return _response(service.complete_task(task_id, authenticated_user.id))
    except (ChoreNotFoundError, ChoreInactiveTaskError, ChorePersistenceError) as error:
        _raise_chore_error(error)
