from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.photos.activity import PhotoActivityService
from app.features.photos.queries import PhotoQueryService
from app.features.photos.service import PhotoService
from app.features.photos.storage import PhotoStorage
from app.features.photos.uploads import UploadBatchService


async def get_photo_storage(request: Request) -> PhotoStorage:
    return PhotoStorage(request.app.state.settings)


def get_photo_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoService:
    return PhotoService(
        session,
        storage,
        request.app.state.settings.photo_default_timezone,
        request.app.state.settings.photo_trash_retention_days,
    )


def get_photo_query_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> PhotoQueryService:
    return PhotoQueryService(session, request.app.state.settings.photo_default_timezone)


def get_photo_activity_service(session: Annotated[Session, Depends(get_session)]) -> PhotoActivityService:
    return PhotoActivityService(session)


def get_upload_batch_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> UploadBatchService:
    return UploadBatchService(session, storage, request.app.state.settings.photo_default_timezone)
