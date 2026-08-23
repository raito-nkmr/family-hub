from datetime import date
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.shopping.dependencies import get_shopping_service, get_shopping_workflow_service
from app.features.shopping.schemas import (
    ShoppingCategoryCreate,
    ShoppingCategoryListResponse,
    ShoppingCategoryOrderUpdate,
    ShoppingCategoryResponse,
    ShoppingCategoryUpdate,
    ShoppingItemCreate,
    ShoppingItemCreateDetailed,
    ShoppingItemListResponse,
    ShoppingItemResponse,
    ShoppingItemUpdate,
    ShoppingListItemListResponse,
    ShoppingListItemResponse,
    ShoppingPurchaseResponse,
    ShoppingPurchaseUpdate,
    ShoppingStatisticsResponse,
    ShoppingTripListResponse,
    ShoppingTripResponse,
    ShoppingTripUpdate,
    ShoppingUnplannedPurchaseCreate,
)
from app.features.shopping.service import (
    ShoppingItemSummary,
    ShoppingNotFoundError,
    ShoppingPersistenceError,
    ShoppingService,
    ShoppingStateConflictError,
)
from app.features.shopping.workflow import (
    ShoppingCategoryDuplicateError,
    ShoppingCategoryInUseError,
    ShoppingCategorySummary,
    ShoppingInvalidCursorError,
    ShoppingInvalidDateRangeError,
    ShoppingListItemSummary,
    ShoppingPurchaseSummary,
    ShoppingTripSummary,
    ShoppingWorkflowConflictError,
    ShoppingWorkflowNotFoundError,
    ShoppingWorkflowPersistenceError,
    ShoppingWorkflowService,
)

router = APIRouter(
    tags=["shopping"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)


def _response(item: ShoppingItemSummary) -> ShoppingItemResponse:
    return ShoppingItemResponse.model_validate(item)


def _category_response(category: ShoppingCategorySummary) -> ShoppingCategoryResponse:
    return ShoppingCategoryResponse.model_validate(category)


def _list_item_response(item: ShoppingListItemSummary) -> ShoppingListItemResponse:
    return ShoppingListItemResponse.model_validate(item)


def _purchase_response(purchase: ShoppingPurchaseSummary) -> ShoppingPurchaseResponse:
    return ShoppingPurchaseResponse(
        id=purchase.id,
        trip_id=purchase.trip_id,
        shopping_item_id=purchase.shopping_item_id,
        item_name=purchase.item_name,
        assignee_user_id=purchase.assignee_user_id,
        assignee_username=purchase.assignee_username,
        category_id=purchase.category_id,
        category_name=purchase.category_name,
        purchased_by_user_id=purchase.purchased_by_user_id,
        purchased_by_username=purchase.purchased_by_username,
        purchased_at=purchase.purchased_at,
        reversed_at=purchase.reversed_at,
        reversed_by_user_id=purchase.reversed_by_user_id,
    )


def _trip_response(trip: ShoppingTripSummary) -> ShoppingTripResponse:
    return ShoppingTripResponse(
        id=trip.id,
        group_id=trip.group_id,
        started_by_user_id=trip.started_by_user_id,
        started_by_username=trip.started_by_username,
        started_at=trip.started_at,
        finalized_at=trip.finalized_at,
        discarded_at=trip.discarded_at,
        discarded_by_user_id=trip.discarded_by_user_id,
        discarded_by_username=trip.discarded_by_username,
        total_amount_yen=trip.total_amount_yen,
        recorded_by_user_id=trip.recorded_by_user_id,
        recorded_by_username=trip.recorded_by_username,
        updated_at=trip.updated_at,
        purchase_count=trip.purchase_count,
        active_purchase_count=trip.active_purchase_count,
        purchases=[_purchase_response(purchase) for purchase in trip.purchases],
    )


def _raise_shopping_error(error: Exception) -> NoReturn:
    if isinstance(error, ShoppingNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping item not found") from error
    if isinstance(error, ShoppingStateConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shopping item state changed") from error
    if isinstance(error, ShoppingPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update shopping item",
        ) from error
    raise error


def _raise_workflow_error(error: Exception) -> NoReturn:
    if isinstance(error, ShoppingWorkflowNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping resource not found") from error
    if isinstance(error, (ShoppingWorkflowConflictError, ShoppingCategoryDuplicateError, ShoppingCategoryInUseError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shopping resource state changed") from error
    if isinstance(error, (ShoppingInvalidCursorError, ShoppingInvalidDateRangeError)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid shopping request"
        ) from error
    if isinstance(error, ShoppingWorkflowPersistenceError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update shopping resource",
        ) from error
    raise error


@router.get("/groups/{group_id}/items", response_model=ShoppingItemListResponse)
def list_shopping_items(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingService, Depends(get_shopping_service)],
) -> ShoppingItemListResponse:
    try:
        return ShoppingItemListResponse(
            items=[_response(item) for item in service.list_items(group_id, authenticated_user.id)]
        )
    except ShoppingNotFoundError as error:
        _raise_shopping_error(error)


@router.post(
    "/groups/{group_id}/items",
    response_model=ShoppingItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_shopping_item(
    group_id: UUID,
    body: ShoppingItemCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingService, Depends(get_shopping_service)],
) -> ShoppingItemResponse:
    try:
        return _response(service.create_item(group_id, authenticated_user.id, body.name))
    except (ShoppingNotFoundError, ShoppingPersistenceError) as error:
        _raise_shopping_error(error)


@router.post(
    "/items/{item_id}/purchase",
    response_model=ShoppingItemResponse,
    dependencies=[Depends(require_csrf_token)],
)
def purchase_shopping_item(
    item_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingService, Depends(get_shopping_service)],
) -> ShoppingItemResponse:
    try:
        return _response(service.purchase_item(item_id, authenticated_user.id))
    except (ShoppingNotFoundError, ShoppingStateConflictError, ShoppingPersistenceError) as error:
        _raise_shopping_error(error)


@router.delete(
    "/items/{item_id}/purchase",
    response_model=ShoppingItemResponse,
    dependencies=[Depends(require_csrf_token)],
)
def restore_shopping_item(
    item_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingService, Depends(get_shopping_service)],
) -> ShoppingItemResponse:
    try:
        return _response(service.restore_item(item_id, authenticated_user.id))
    except (ShoppingNotFoundError, ShoppingStateConflictError, ShoppingPersistenceError) as error:
        _raise_shopping_error(error)


@router.get("/groups/{group_id}/requests", response_model=ShoppingListItemListResponse)
def list_shopping_requests(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingListItemListResponse:
    try:
        return ShoppingListItemListResponse(
            items=[_list_item_response(item) for item in service.list_items(group_id, authenticated_user.id)]
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.post(
    "/groups/{group_id}/requests",
    response_model=ShoppingListItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_shopping_request(
    group_id: UUID,
    body: ShoppingItemCreateDetailed,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingListItemResponse:
    try:
        return _list_item_response(
            service.create_item(
                group_id,
                authenticated_user.id,
                body.name,
                body.assignee_user_id,
                body.category_id,
            )
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.patch(
    "/requests/{item_id}",
    response_model=ShoppingListItemResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_shopping_request(
    item_id: UUID,
    body: ShoppingItemUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingListItemResponse:
    try:
        return _list_item_response(
            service.update_item(
                item_id,
                authenticated_user.id,
                body.name,
                body.assignee_user_id,
                body.category_id,
            )
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.delete(
    "/requests/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_shopping_request(
    item_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> Response:
    try:
        service.delete_item(item_id, authenticated_user.id)
    except Exception as error:
        _raise_workflow_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/groups/{group_id}/categories", response_model=ShoppingCategoryListResponse)
def list_shopping_categories(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingCategoryListResponse:
    try:
        return ShoppingCategoryListResponse(
            items=[
                _category_response(category) for category in service.list_categories(group_id, authenticated_user.id)
            ]
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.post(
    "/groups/{group_id}/categories",
    response_model=ShoppingCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def create_shopping_category(
    group_id: UUID,
    body: ShoppingCategoryCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingCategoryResponse:
    try:
        return _category_response(service.create_category(group_id, authenticated_user.id, body.name))
    except Exception as error:
        _raise_workflow_error(error)


@router.patch(
    "/categories/{category_id}",
    response_model=ShoppingCategoryResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_shopping_category(
    category_id: UUID,
    body: ShoppingCategoryUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingCategoryResponse:
    try:
        return _category_response(service.update_category(category_id, authenticated_user.id, body.name))
    except Exception as error:
        _raise_workflow_error(error)


@router.patch(
    "/groups/{group_id}/categories/order",
    response_model=ShoppingCategoryListResponse,
    dependencies=[Depends(require_csrf_token)],
)
def reorder_shopping_categories(
    group_id: UUID,
    body: ShoppingCategoryOrderUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingCategoryListResponse:
    try:
        return ShoppingCategoryListResponse(
            items=[
                _category_response(category)
                for category in service.reorder_categories(group_id, authenticated_user.id, body.category_ids)
            ]
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_shopping_category(
    category_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> Response:
    try:
        service.delete_category(category_id, authenticated_user.id)
    except Exception as error:
        _raise_workflow_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/groups/{group_id}/trips",
    response_model=ShoppingTripResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def start_shopping_trip(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingTripResponse:
    try:
        return _trip_response(service.start_trip(group_id, authenticated_user.id))
    except Exception as error:
        _raise_workflow_error(error)


@router.get("/groups/{group_id}/trips", response_model=ShoppingTripListResponse)
def list_shopping_trips(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> ShoppingTripListResponse:
    try:
        items, next_cursor = service.list_trips(group_id, authenticated_user.id, cursor, limit)
        return ShoppingTripListResponse(items=[_trip_response(item) for item in items], next_cursor=next_cursor)
    except Exception as error:
        _raise_workflow_error(error)


@router.get("/trips/{trip_id}", response_model=ShoppingTripResponse)
def get_shopping_trip(
    trip_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingTripResponse:
    try:
        return _trip_response(service.get_trip(trip_id, authenticated_user.id))
    except Exception as error:
        _raise_workflow_error(error)


@router.patch(
    "/trips/{trip_id}",
    response_model=ShoppingTripResponse | None,
    dependencies=[Depends(require_csrf_token)],
)
def update_shopping_trip(
    trip_id: UUID,
    body: ShoppingTripUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingTripResponse | None:
    try:
        trip = service.update_trip(
            trip_id,
            authenticated_user.id,
            body.total_amount_yen,
            body.finalize,
            body.delete_if_empty,
        )
        return _trip_response(trip) if trip is not None else None
    except Exception as error:
        _raise_workflow_error(error)


@router.post(
    "/trips/{trip_id}/discard",
    response_model=ShoppingTripResponse,
    dependencies=[Depends(require_csrf_token)],
)
def discard_shopping_trip(
    trip_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingTripResponse:
    try:
        return _trip_response(service.discard_trip(trip_id, authenticated_user.id))
    except Exception as error:
        _raise_workflow_error(error)


@router.delete(
    "/trips/{trip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_token)],
)
def delete_empty_shopping_trip(
    trip_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> Response:
    try:
        service.delete_empty_trip(trip_id, authenticated_user.id)
    except Exception as error:
        _raise_workflow_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/requests/{item_id}/purchase",
    response_model=ShoppingPurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def purchase_shopping_request(
    item_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
    trip_id: UUID | None = None,
) -> ShoppingPurchaseResponse:
    try:
        return _purchase_response(service.purchase_item(item_id, authenticated_user.id, trip_id))
    except Exception as error:
        _raise_workflow_error(error)


@router.post(
    "/trips/{trip_id}/purchases",
    response_model=ShoppingPurchaseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_token)],
)
def add_unplanned_shopping_purchase(
    trip_id: UUID,
    body: ShoppingUnplannedPurchaseCreate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingPurchaseResponse:
    try:
        return _purchase_response(
            service.add_unplanned_purchase(
                trip_id,
                authenticated_user.id,
                body.name,
                body.category_id,
                body.purchased_by_user_id,
            )
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.patch(
    "/purchases/{purchase_id}",
    response_model=ShoppingPurchaseResponse,
    dependencies=[Depends(require_csrf_token)],
)
def update_shopping_purchase(
    purchase_id: UUID,
    body: ShoppingPurchaseUpdate,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingPurchaseResponse:
    try:
        return _purchase_response(
            service.update_purchase(
                purchase_id,
                authenticated_user.id,
                body.category_id,
                body.purchased_by_user_id,
            )
        )
    except Exception as error:
        _raise_workflow_error(error)


@router.post(
    "/purchases/{purchase_id}/reverse",
    response_model=ShoppingPurchaseResponse,
    dependencies=[Depends(require_csrf_token)],
)
def reverse_shopping_purchase(
    purchase_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
) -> ShoppingPurchaseResponse:
    try:
        return _purchase_response(service.reverse_purchase(purchase_id, authenticated_user.id))
    except Exception as error:
        _raise_workflow_error(error)


@router.get("/groups/{group_id}/statistics", response_model=ShoppingStatisticsResponse)
def get_shopping_statistics(
    group_id: UUID,
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ShoppingWorkflowService, Depends(get_shopping_workflow_service)],
    from_date: date,
    to_date: date,
) -> ShoppingStatisticsResponse:
    try:
        return ShoppingStatisticsResponse.model_validate(
            service.statistics(group_id, authenticated_user.id, from_date, to_date)
        )
    except Exception as error:
        _raise_workflow_error(error)
