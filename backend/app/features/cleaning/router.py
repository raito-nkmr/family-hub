from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.cleaning.dependencies import get_cleaning_service
from app.features.cleaning.schemas import (
    CleaningTaskCreate,
    CleaningTaskListResponse,
    CleaningTaskResponse,
    CleaningTaskUpdate,
)
from app.features.cleaning.service import (
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
                body.category,
            )
        )
    except (CleaningNotFoundError, CleaningForbiddenError, CleaningPersistenceError) as error:
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
                category=body.category,
                interval_days=body.interval_days,
                is_active=body.is_active,
            )
        )
    except (CleaningNotFoundError, CleaningForbiddenError, CleaningPersistenceError) as error:
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
