from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.features.auth.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_csrf_token,
    require_password_change_complete,
)
from app.features.shopping.dependencies import get_shopping_service
from app.features.shopping.schemas import ShoppingItemCreate, ShoppingItemListResponse, ShoppingItemResponse
from app.features.shopping.service import (
    ShoppingItemSummary,
    ShoppingNotFoundError,
    ShoppingPersistenceError,
    ShoppingService,
    ShoppingStateConflictError,
)

router = APIRouter(
    tags=["shopping"],
    dependencies=[Depends(require_authenticated_user), Depends(require_password_change_complete)],
)


def _response(item: ShoppingItemSummary) -> ShoppingItemResponse:
    return ShoppingItemResponse.model_validate(item)


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
