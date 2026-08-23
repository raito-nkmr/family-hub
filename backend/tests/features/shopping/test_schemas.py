import pytest
from pydantic import ValidationError

from app.features.shopping.schemas import ShoppingItemCreate, ShoppingPurchaseUpdate, ShoppingTripUpdate


def test_shopping_item_create_trims_name() -> None:
    assert ShoppingItemCreate(name="  牛乳  ").name == "牛乳"


def test_shopping_item_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ShoppingItemCreate(name="   ")


def test_shopping_trip_amount_allows_unrecorded_or_nonnegative_yen() -> None:
    assert ShoppingTripUpdate(total_amount_yen=None).total_amount_yen is None
    assert ShoppingTripUpdate(total_amount_yen=1250).total_amount_yen == 1250
    with pytest.raises(ValidationError):
        ShoppingTripUpdate(total_amount_yen=-1)


def test_shopping_trip_amount_omission_is_distinguishable_from_explicit_null() -> None:
    assert "total_amount_yen" not in ShoppingTripUpdate().model_fields_set
    assert "total_amount_yen" in ShoppingTripUpdate(total_amount_yen=None).model_fields_set


def test_shopping_purchase_update_requires_a_purchaser_when_present() -> None:
    assert ShoppingPurchaseUpdate().purchased_by_user_id is None
    with pytest.raises(ValidationError):
        ShoppingPurchaseUpdate(purchased_by_user_id=None)
