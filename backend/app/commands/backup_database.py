import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.maintenance.models import MaintenanceJobType, MaintenanceRunStatus
from app.features.maintenance.service import MaintenanceService
from app.features.photos.storage import PhotoStorage


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _postgres_environment(database_url: str) -> tuple[dict[str, str], str]:
    url = make_url(database_url)
    if not url.database:
        raise RuntimeError("DATABASE_URL must include a database name")
    process_environment = os.environ.copy()
    mappings = {
        "PGHOST": url.host,
        "PGPORT": str(url.port) if url.port else None,
        "PGUSER": url.username,
        "PGPASSWORD": url.password,
    }
    for key, value in mappings.items():
        if value is not None:
            process_environment[key] = value
    return process_environment, url.database


def main() -> None:
    settings = get_management_settings()
    if settings.database_url is None or settings.photo_storage_root is None:
        raise SystemExit("DATABASE_URL and PHOTO_STORAGE_ROOT must be configured")
    storage = PhotoStorage(settings)
    if not storage.get_status().available:
        raise SystemExit("Photo storage is unavailable or not writable")

    engine = create_database_engine(settings)
    try:
        with Session(engine, expire_on_commit=False) as session:
            maintenance = MaintenanceService(session, storage)
            run = maintenance.start_run(MaintenanceJobType.DATABASE_BACKUP)
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            directory = settings.photo_storage_root / "database-backups" / timestamp[:4] / timestamp[4:6]
            directory.mkdir(parents=True, exist_ok=True)
            final_path = directory / f"family-hub-{timestamp}.dump"
            part_path = final_path.with_suffix(".dump.part")
            manifest_path = final_path.with_suffix(".json")
            try:
                process_environment, database_name = _postgres_environment(settings.database_url)
                subprocess.run(
                    [
                        "pg_dump",
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                        "--file",
                        str(part_path),
                        database_name,
                    ],
                    env=process_environment,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                part_path.chmod(0o600)
                digest = _sha256(part_path)
                part_path.replace(final_path)
                manifest = {
                    "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "filename": final_path.name,
                    "size_bytes": final_path.stat().st_size,
                    "sha256": digest,
                }
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                manifest_path.chmod(0o600)
                maintenance.finish_run(run, MaintenanceRunStatus.SUCCEEDED, summary=manifest)
            except Exception as error:
                part_path.unlink(missing_ok=True)
                maintenance.finish_run(
                    run,
                    MaintenanceRunStatus.FAILED,
                    error_code="database_backup_failed",
                    error_message=type(error).__name__,
                )
                raise
    finally:
        engine.dispose()

    print(f"Created database backup {final_path}")


if __name__ == "__main__":
    main()
