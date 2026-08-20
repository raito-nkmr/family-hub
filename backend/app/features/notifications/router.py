from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.features.auth.dependencies import get_auth_context, require_csrf_token, require_password_change_complete
from app.features.auth.public import AuthContext
from app.features.notifications.dependencies import get_notification_service
from app.features.notifications.schemas import (
    NotificationConfigResponse,
    NotificationPreferenceItem,
    NotificationPreferenceUpdate,
    PushSubscriptionCreate,
    PushSubscriptionLocaleUpdate,
    PushSubscriptionResponse,
)
from app.features.notifications.service import (
    NotificationEndpointNotAllowedError,
    NotificationPersistenceError,
    NotificationService,
    NotificationSubscriptionEndpointConflictError,
    NotificationSubscriptionLimitError,
)

router = APIRouter(tags=["notifications"], dependencies=[Depends(require_password_change_complete)])


@router.get("/config", response_model=NotificationConfigResponse)
def get_notification_config(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationConfigResponse:
    return NotificationConfigResponse.model_validate(service.config(context))


@router.post(
    "/subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_push_subscription(
    body: PushSubscriptionCreate,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> PushSubscriptionResponse:
    try:
        return PushSubscriptionResponse.model_validate(service.subscribe(context, body))
    except NotificationEndpointNotAllowedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Push endpoint is not allowed",
        ) from error
    except NotificationSubscriptionEndpointConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "push_subscription_endpoint_conflict",
                "message": "Push subscription endpoint belongs to another user",
            },
        ) from error
    except NotificationSubscriptionLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "push_subscription_limit_reached", "message": "Push subscription limit reached"},
        ) from error
    except NotificationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Web Push is unavailable"
        ) from error


@router.delete(
    "/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_push_subscription(
    subscription_id: UUID,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> None:
    try:
        service.unsubscribe(context, subscription_id)
    except NotificationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Web Push is unavailable"
        ) from error


@router.put(
    "/subscriptions/locale",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def update_push_subscription_locale(
    body: PushSubscriptionLocaleUpdate,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> None:
    try:
        service.update_subscription_locale(context, body)
    except NotificationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Web Push is unavailable"
        ) from error


@router.put(
    "/preferences",
    response_model=list[NotificationPreferenceItem],
    dependencies=[Depends(require_csrf_token)],
)
def update_notification_preferences(
    body: NotificationPreferenceUpdate,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[NotificationPreferenceItem]:
    try:
        return service.update_preferences(context.user.id, body.items)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except NotificationPersistenceError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Web Push is unavailable"
        ) from error
