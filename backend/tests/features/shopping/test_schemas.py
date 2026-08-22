import pytest
from pydantic import ValidationError

from app.features.shopping.schemas import ShoppingItemCreate, ShoppingTripUpdate


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
