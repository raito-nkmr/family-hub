from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.features.maintenance.models import MaintenanceJobType, MaintenanceRun, MaintenanceRunStatus
from app.features.photos.public import Photo, PhotoLifecycleState, PhotoStorage


class MaintenancePersistenceError(Exception):
    pass


class MaintenanceService:
    def __init__(self, session: Session, storage: PhotoStorage) -> None:
        self._session = session
        self._storage = storage

    def start_run(self, job_type: MaintenanceJobType) -> MaintenanceRun:
        run = MaintenanceRun(
            id=uuid4(),
            job_type=job_type,
            status=MaintenanceRunStatus.RUNNING,
            started_at=datetime.now(UTC),
            finished_at=None,
            summary={},
            error_code=None,
            error_message=None,
        )
        self._session.add(run)
        self._commit()
        return run

    def finish_run(
        self,
        run: MaintenanceRun,
        status: MaintenanceRunStatus,
        *,
        summary: dict[str, object] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> MaintenanceRun:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.summary = summary or {}
        run.error_code = error_code
        run.error_message = error_message[:2000] if error_message else None
        self._commit()
        return run

    def fail_run(self, run: MaintenanceRun, *, error_code: str, error: BaseException) -> MaintenanceRun:
        return self.finish_run(
            run,
            MaintenanceRunStatus.FAILED,
            error_code=error_code,
            error_message=type(error).__name__,
        )

    def latest_runs(self) -> list[MaintenanceRun]:
        items = []
        for job_type in MaintenanceJobType:
            run = self._session.scalar(
                select(MaintenanceRun)
                .where(MaintenanceRun.job_type == job_type)
                .order_by(MaintenanceRun.started_at.desc(), MaintenanceRun.id.desc())
                .limit(1)
            )
            if run is not None:
                items.append(run)
        return items

    def history(self, limit: int = 100) -> list[MaintenanceRun]:
        return list(
            self._session.scalars(
                select(MaintenanceRun).order_by(MaintenanceRun.started_at.desc(), MaintenanceRun.id.desc()).limit(limit)
            ).all()
        )

    def system_status(self) -> dict[str, object]:
        storage = self._storage.get_status()
        active_count, active_bytes = self._photo_totals(PhotoLifecycleState.ACTIVE)
        trashed_count, trashed_bytes = self._photo_totals(
            (PhotoLifecycleState.TRASHED, PhotoLifecycleState.PURGE_PENDING)
        )
        latest_runs = self.latest_runs()
        alerts = []
        if not storage.available:
            alerts.append("storage_unavailable")
        elif not storage.writable:
            alerts.append("storage_not_writable")
        if any(run.status == MaintenanceRunStatus.FAILED for run in latest_runs):
            alerts.append("maintenance_failed")
        return {
            "storage": {
                "status": storage.status,
                "available": storage.available,
                "writable": storage.writable,
                "free_bytes": storage.free_bytes,
                "total_bytes": storage.total_bytes,
                "minimum_free_bytes": storage.minimum_free_bytes,
                "active_photo_count": active_count,
                "active_photo_bytes": active_bytes,
                "trashed_photo_count": trashed_count,
                "trashed_photo_bytes": trashed_bytes,
            },
            "latest_runs": latest_runs,
            "alerts": alerts,
        }

    def _photo_totals(self, state: PhotoLifecycleState | tuple[PhotoLifecycleState, ...]) -> tuple[int, int]:
        condition = Photo.lifecycle_state.in_(state) if isinstance(state, tuple) else Photo.lifecycle_state == state
        row = self._session.execute(
            select(func.count(Photo.id), func.coalesce(func.sum(Photo.size_bytes), 0)).where(condition)
        ).one()
        return int(row[0]), int(row[1])

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise MaintenancePersistenceError from error
