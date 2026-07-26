from sqlalchemy import inspect

from app.features.shopping.models import ShoppingItem


def test_shopping_item_has_group_and_purchase_state_constraints() -> None:
    table = inspect(ShoppingItem).local_table

    assert {constraint.name for constraint in table.constraints} >= {
        "pk_shopping_items",
        "ck_shopping_items_name_trimmed",
        "ck_shopping_items_name_length",
        "ck_shopping_items_purchase_state",
        "fk_shopping_items_group_id_family_groups",
        "fk_shopping_items_created_by_user_id_users",
        "fk_shopping_items_purchased_by_user_id_users",
    }
