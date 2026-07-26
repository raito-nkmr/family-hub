from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.features.auth.dependencies import require_system_admin
from app.features.maintenance.dependencies import get_maintenance_service
from app.features.maintenance.schemas import MaintenanceRunListResponse, MaintenanceRunResponse, SystemStatusResponse
from app.features.maintenance.service import MaintenanceService

router = APIRouter(tags=["admin maintenance"], dependencies=[Depends(require_system_admin)])


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(
    service: Annotated[MaintenanceService, Depends(get_maintenance_service)],
) -> SystemStatusResponse:
    return SystemStatusResponse.model_validate(service.system_status())


@router.get("/history", response_model=MaintenanceRunListResponse)
def list_maintenance_history(
    service: Annotated[MaintenanceService, Depends(get_maintenance_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> MaintenanceRunListResponse:
    return MaintenanceRunListResponse(
        items=[MaintenanceRunResponse.model_validate(run) for run in service.history(limit)]
    )
