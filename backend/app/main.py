import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.lifespan import create_lifespan
from app.core.middleware import (
    PrivateApiCacheControlMiddleware,
    RequestLoggingMiddleware,
    SinglePhotoUploadSizeLimitMiddleware,
)
from app.features.albums.router import router as albums_router
from app.features.auth.admin_router import router as admin_router
from app.features.auth.invitation_router import admin_router as admin_invitation_router
from app.features.auth.invitation_router import public_router as invitation_router
from app.features.auth.router import router as auth_router
from app.features.cleaning.router import router as cleaning_router
from app.features.groups.router import router as groups_router
from app.features.health.router import root_router
from app.features.health.router import router as health_router
from app.features.maintenance.router import router as maintenance_router
from app.features.notifications.router import router as notifications_router
from app.features.photos.router import router as photos_router
from app.features.photos.upload_router import router as upload_batches_router
from app.features.shopping.router import router as shopping_router

logger = logging.getLogger(__name__)


async def log_http_exception(request: Request, error: HTTPException):
    if error.status_code >= 500:
        cause = error.__cause__
        logger.error(
            "HTTP error method=%s path=%s status=%s error_type=%s",
            request.method,
            request.url.path,
            error.status_code,
            type(cause or error).__name__,
            exc_info=(type(cause), cause, cause.__traceback__) if cause is not None else None,
        )
    return await http_exception_handler(request, error)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(lifespan=create_lifespan(app_settings))
    app.add_middleware(
        SinglePhotoUploadSizeLimitMiddleware,
        maximum_upload_bytes=app_settings.photo_max_upload_bytes,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Upload-Offset"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(PrivateApiCacheControlMiddleware)
    app.add_exception_handler(HTTPException, log_http_exception)
    app.include_router(root_router)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1/auth")
    app.include_router(invitation_router, prefix="/api/v1/auth/invitations")
    app.include_router(admin_invitation_router, prefix="/api/v1/admin/invitations")
    app.include_router(admin_router, prefix="/api/v1/admin")
    app.include_router(photos_router, prefix="/api/v1/photos")
    app.include_router(upload_batches_router, prefix="/api/v1/upload-batches")
    app.include_router(albums_router, prefix="/api/v1/albums")
    app.include_router(groups_router, prefix="/api/v1/groups")
    app.include_router(cleaning_router, prefix="/api/v1/cleaning")
    app.include_router(shopping_router, prefix="/api/v1/shopping")
    app.include_router(maintenance_router, prefix="/api/v1/admin/maintenance")
    app.include_router(notifications_router, prefix="/api/v1/notifications")
    return app


app = create_app()
