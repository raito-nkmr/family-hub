from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.photos.access_service import PhotoAccessService
from app.features.photos.activity import PhotoActivityService
from app.features.photos.export_service import PhotoExportService
from app.features.photos.metadata_service import PhotoMetadataService
from app.features.photos.queries import PhotoQueryService
from app.features.photos.storage import PhotoStorage
from app.features.photos.trash_service import PhotoTrashService
from app.features.photos.upload_service import PhotoUploadService
from app.features.photos.uploads import UploadBatchService


async def get_photo_storage(request: Request) -> PhotoStorage:
    return PhotoStorage(request.app.state.settings)


def get_photo_access_service(
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoAccessService:
    return PhotoAccessService(session, storage)


def get_photo_metadata_service(
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoMetadataService:
    return PhotoMetadataService(session, storage)


def get_photo_upload_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoUploadService:
    return PhotoUploadService(session, storage, request.app.state.settings.photo_default_timezone)


def get_photo_trash_service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoTrashService:
    return PhotoTrashService(session, storage, request.app.state.settings.photo_trash_retention_days)


def get_photo_export_service(
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_photo_storage)],
) -> PhotoExportService:
    return PhotoExportService(session, storage)


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
