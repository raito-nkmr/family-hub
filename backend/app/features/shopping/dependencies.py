from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.auth.public import UserDirectory
from app.features.shopping.service import ShoppingService


def get_shopping_service(session: Annotated[Session, Depends(get_session)]) -> ShoppingService:
    return ShoppingService(session, UserDirectory(session))
