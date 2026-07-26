import shutil
import subprocess
from datetime import UTC, datetime
from hmac import compare_digest
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.maintenance.models import MaintenanceJobType, MaintenanceRunStatus
from app.features.maintenance.service import MaintenanceService
from app.features.photos.storage import PhotoStorage

BACKUP_MARKER_FILENAME = ".family-hub-backup-marker"


def _require_backup_root(root: Path | None, expected_marker: str | None, primary_root: Path | None) -> Path:
    if root is None or not expected_marker or primary_root is None:
        raise RuntimeError("Backup storage is not configured")
    absolute_root = Path(root.absolute())
    if absolute_root.is_symlink() or not absolute_root.is_dir() or not absolute_root.is_mount():
        raise RuntimeError("Backup storage root must be a mounted directory without symlinks")
    if absolute_root.resolve(strict=True) == primary_root.resolve(strict=True):
        raise RuntimeError("Backup storage must differ from primary photo storage")
    marker = absolute_root / BACKUP_MARKER_FILENAME
    if marker.is_symlink() or not marker.is_file():
        raise RuntimeError("Backup storage marker is missing")
    if not compare_digest(marker.read_bytes().strip(), expected_marker.encode("utf-8")):
        raise RuntimeError("Backup storage marker does not match")
    return absolute_root


def main() -> None:
    settings = get_management_settings()
    primary_storage = PhotoStorage(settings)
    if not primary_storage.get_read_status().available:
        raise SystemExit("Primary photo storage is unavailable")
    try:
        backup_root = _require_backup_root(
            settings.backup_storage_root,
            settings.backup_storage_marker,
            settings.photo_storage_root,
        )
    except RuntimeError as error:
        raise SystemExit(str(error)) from error

    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            maintenance = MaintenanceService(session, primary_storage)
            run = maintenance.start_run(MaintenanceJobType.SECONDARY_STORAGE_BACKUP)
            snapshot_name = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            snapshots_root = backup_root / "snapshots"
            snapshots_root.mkdir(exist_ok=True)
            incomplete = snapshots_root / f".incomplete-{snapshot_name}"
            final = snapshots_root / snapshot_name
            previous = max(
                (path for path in snapshots_root.iterdir() if path.is_dir() and not path.name.startswith(".")),
                default=None,
            )
            try:
                incomplete.mkdir()
                assert settings.photo_storage_root is not None
                for directory_name in ("originals", "database-backups"):
                    source = settings.photo_storage_root / directory_name
                    destination = incomplete / directory_name
                    destination.mkdir()
                    command = ["rsync", "--archive", "--delete"]
                    if previous is not None:
                        command.append(f"--link-dest={previous / directory_name}")
                    command.extend([f"{source}/", f"{destination}/"])
                    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                incomplete.replace(final)
                summary = {
                    "snapshot": snapshot_name,
                    "previous_snapshot": previous.name if previous else None,
                    "free_bytes": shutil.disk_usage(backup_root).free,
                }
                maintenance.finish_run(run, MaintenanceRunStatus.SUCCEEDED, summary=summary)
            except Exception as error:
                shutil.rmtree(incomplete, ignore_errors=True)
                maintenance.finish_run(
                    run,
                    MaintenanceRunStatus.FAILED,
                    error_code="secondary_storage_backup_failed",
                    error_message=type(error).__name__,
                )
                raise
    finally:
        engine.dispose()
    print(f"Created secondary storage snapshot {final}")


if __name__ == "__main__":
    main()
