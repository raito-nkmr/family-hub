from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.albums.service import AlbumService
from app.features.photos.public import PhotoAlbumSharingService, PhotoCatalog, PhotoStorage, get_photo_storage


def get_album_service(
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> AlbumService:
    return AlbumService(session, PhotoCatalog(session), PhotoAlbumSharingService(session, storage))
