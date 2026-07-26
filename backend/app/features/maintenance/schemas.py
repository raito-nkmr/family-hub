from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.maintenance.models import MaintenanceJobType, MaintenanceRunStatus
from app.features.photos.public import StorageStatusCode


class MaintenanceRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: MaintenanceJobType
    status: MaintenanceRunStatus
    started_at: datetime
    finished_at: datetime | None
    summary: dict[str, object]
    error_code: str | None
    error_message: str | None


class AdministrativeStorageStatusResponse(BaseModel):
    status: StorageStatusCode
    available: bool
    writable: bool
    free_bytes: int | None
    total_bytes: int | None
    minimum_free_bytes: int | None
    active_photo_count: int
    active_photo_bytes: int
    trashed_photo_count: int
    trashed_photo_bytes: int


class SystemStatusResponse(BaseModel):
    storage: AdministrativeStorageStatusResponse
    latest_runs: list[MaintenanceRunResponse]
    alerts: list[str]


class MaintenanceRunListResponse(BaseModel):
    items: list[MaintenanceRunResponse]
