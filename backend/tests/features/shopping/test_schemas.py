import pytest
from pydantic import ValidationError

from app.features.shopping.schemas import ShoppingItemCreate


def test_shopping_item_create_trims_name() -> None:
    assert ShoppingItemCreate(name="  牛乳  ").name == "牛乳"


def test_shopping_item_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        ShoppingItemCreate(name="   ")
