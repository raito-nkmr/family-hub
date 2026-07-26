from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.albums.service import AlbumService
from app.features.photos.public import PhotoCatalog


def get_album_service(session: Annotated[Session, Depends(get_session)]) -> AlbumService:
    return AlbumService(session, PhotoCatalog(session))
