import argparse

from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.maintenance.models import MaintenanceJobType, MaintenanceRunStatus
from app.features.maintenance.service import MaintenanceService
from app.features.photos.storage import PhotoStorage
from app.features.photos.trash_service import PhotoTrashService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Permanently delete expired photos from the trash")
    parser.add_argument("--limit", type=int, default=100, choices=range(1, 1001), metavar="1-1000")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_management_settings()
    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            storage = PhotoStorage(settings)
            maintenance = MaintenanceService(session, storage)
            run = maintenance.start_run(MaintenanceJobType.TRASH_PURGE)
            service = PhotoTrashService(
                session,
                storage,
                settings.photo_default_timezone,
                settings.photo_trash_retention_days,
            )
            try:
                purged_count = service.purge_due_photos(limit=args.limit)
            except BaseException as error:
                maintenance.fail_run(run, error_code="trash_purge_failed", error=error)
                raise
            maintenance.finish_run(
                run,
                MaintenanceRunStatus.SUCCEEDED,
                summary={"purged_photo_count": purged_count},
            )
    finally:
        engine.dispose()
    print(f"Permanently deleted {purged_count} expired photo(s)")


if __name__ == "__main__":
    main()
