import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.features.photos.public import PhotoStorage

router = APIRouter(tags=["health"])
root_router = APIRouter()
logger = logging.getLogger(__name__)


class RootResponse(BaseModel):
    message: str
    health: str
    docs: str


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["available", "unavailable"]
    photo_storage: str


def get_readiness_storage(request: Request) -> PhotoStorage:
    return PhotoStorage(request.app.state.settings)


@root_router.get("/", response_model=RootResponse, include_in_schema=False)
async def get_root() -> RootResponse:
    return RootResponse(
        message="Family Hub API is running",
        health="/api/v1/health",
        docs="/docs",
    )


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


def _check_readiness(session: Session, storage: PhotoStorage) -> tuple[bool, bool, str]:
    database_available = True
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        session.rollback()
        logger.warning("Readiness database check failed error_type=%s", type(error).__name__)
        database_available = False

    storage_status = storage.get_read_status()
    return database_available, storage_status.available, storage_status.status


@router.get("/readiness", response_model=ReadinessResponse, include_in_schema=False)
async def get_readiness(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[PhotoStorage, Depends(get_readiness_storage)],
) -> ReadinessResponse:
    database_available, storage_available, storage_status = _check_readiness(session, storage)
    ready = database_available and storage_available
    if not ready:
        logger.warning(
            "Application is not ready database_available=%s storage_available=%s storage_status=%s",
            database_available,
            storage_available,
            storage_status,
        )
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        database="available" if database_available else "unavailable",
        photo_storage=storage_status,
    )
