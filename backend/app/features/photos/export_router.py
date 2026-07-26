from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.features.auth.dependencies import AuthenticatedUser, require_authenticated_user
from app.features.photos.dependencies import get_photo_service
from app.features.photos.export import stream_photo_export
from app.features.photos.schemas import PhotoExportRequest
from app.features.photos.service import (
    PhotoContentUnavailableError,
    PhotoExportSelectionError,
    PhotoService,
)

router = APIRouter()


@router.get("/export", response_class=StreamingResponse)
def export_photo_originals(
    body: Annotated[PhotoExportRequest, Query()],
    authenticated_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[PhotoService, Depends(get_photo_service)],
) -> StreamingResponse:
    try:
        entries = service.get_photo_export_entries(body.photo_ids, authenticated_user.id)
    except PhotoExportSelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="One or more photos were not found"
        ) from error
    except PhotoContentUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Photo content unavailable"
        ) from error
    return StreamingResponse(
        stream_photo_export(entries),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="family-hub-photos.zip"',
            "Cache-Control": "private, no-store",
        },
    )
