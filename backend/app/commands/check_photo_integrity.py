import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.maintenance.models import MaintenanceJobType, MaintenanceRunStatus
from app.features.maintenance.service import MaintenanceService
from app.features.photos.models import Photo, UploadItem, UploadItemStatus
from app.features.photos.registration import build_sidecar_metadata
from app.features.photos.storage.facade import PhotoStorage, PhotoStorageError


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    code: str
    path: str
    photo_id: str | None = None


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    checked_photos: int
    checked_derivatives: int
    issues: tuple[IntegrityIssue, ...]

    @property
    def clean(self) -> bool:
        return not self.issues


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def check_photo_integrity(
    session: Session,
    storage: PhotoStorage,
    storage_root: Path,
    derivative_root: Path,
    *,
    verify_hashes: bool = False,
) -> IntegrityReport:
    photos = session.scalars(select(Photo).order_by(Photo.id)).all()
    issues: list[IntegrityIssue] = []
    expected_originals: set[Path] = set()
    expected_sidecars: set[Path] = set()
    expected_derivatives: set[Path] = set()
    expected_storage_parts: set[Path] = set()
    expected_derivative_parts: set[Path] = set()
    checked_derivatives = 0

    active_item_ids = session.scalars(
        select(UploadItem.id).where(
            UploadItem.status.in_([UploadItemStatus.QUEUED, UploadItemStatus.UPLOADING, UploadItemStatus.PROCESSING])
        )
    ).all()
    for item_id in active_item_ids:
        expected_storage_parts.update(
            {
                storage_root / "incoming" / f"{item_id}.part",
                storage_root / "incoming" / f"{item_id}.json.part",
            }
        )
        expected_derivative_parts.add(derivative_root / "incoming" / f"{item_id}.thumbnail.part")

    for photo in photos:
        photo_id = str(photo.id)
        try:
            original_path, sidecar_path = storage.get_original_file_paths(photo.storage_key)
        except PhotoStorageError:
            issues.append(IntegrityIssue("original_invalid", str(storage_root / "<invalid-storage-key>"), photo_id))
            original_path = sidecar_path = storage_root / "<invalid-storage-key>"
        else:
            expected_originals.add(original_path)
            expected_sidecars.add(sidecar_path)

            try:
                verified_original_path = storage.get_original_path(photo.storage_key)
            except PhotoStorageError:
                issues.append(IntegrityIssue("original_missing", str(original_path), photo_id))
            else:
                try:
                    if verified_original_path.stat().st_size != photo.size_bytes:
                        issues.append(IntegrityIssue("original_size_mismatch", str(verified_original_path), photo_id))
                    if verify_hashes and _file_sha256(verified_original_path) != photo.sha256:
                        issues.append(IntegrityIssue("original_hash_mismatch", str(verified_original_path), photo_id))
                except OSError:
                    issues.append(IntegrityIssue("original_unreadable", str(verified_original_path), photo_id))

            if sidecar_path.is_symlink():
                issues.append(IntegrityIssue("sidecar_invalid", str(sidecar_path), photo_id))
            else:
                try:
                    actual_sidecar = _load_json(sidecar_path)
                except FileNotFoundError:
                    issues.append(IntegrityIssue("sidecar_missing", str(sidecar_path), photo_id))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    issues.append(IntegrityIssue("sidecar_invalid", str(sidecar_path), photo_id))
                else:
                    if actual_sidecar != build_sidecar_metadata(photo).as_json():
                        issues.append(IntegrityIssue("sidecar_mismatch", str(sidecar_path), photo_id))

        for derivative in photo.derivatives:
            checked_derivatives += 1
            try:
                derivative_path = storage.get_derivative_file_path(derivative.storage_key)
            except PhotoStorageError:
                issues.append(
                    IntegrityIssue("derivative_invalid", str(derivative_root / "<invalid-storage-key>"), photo_id)
                )
                continue
            expected_derivatives.add(derivative_path)
            try:
                verified_derivative_path = storage.get_derivative_path(derivative.storage_key)
            except PhotoStorageError:
                issues.append(IntegrityIssue("derivative_missing", str(derivative_path), photo_id))
            else:
                try:
                    if verified_derivative_path.stat().st_size != derivative.size_bytes:
                        issues.append(
                            IntegrityIssue("derivative_size_mismatch", str(verified_derivative_path), photo_id)
                        )
                except OSError:
                    issues.append(IntegrityIssue("derivative_unreadable", str(verified_derivative_path), photo_id))

    originals_root = storage_root / "originals"
    if originals_root.is_dir():
        for path in originals_root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            if path.suffix == ".json":
                if path not in expected_sidecars:
                    issues.append(IntegrityIssue("orphan_sidecar", str(path)))
            elif path not in expected_originals:
                issues.append(IntegrityIssue("orphan_original", str(path)))

    thumbnails_root = derivative_root / "thumbnails"
    if thumbnails_root.is_dir():
        for path in thumbnails_root.rglob("*"):
            if path.is_file() and not path.is_symlink() and path not in expected_derivatives:
                issues.append(IntegrityIssue("orphan_derivative", str(path)))

    for incoming_root, expected_parts in (
        (storage_root / "incoming", expected_storage_parts),
        (derivative_root / "incoming", expected_derivative_parts),
    ):
        if not incoming_root.is_dir():
            continue
        for path in incoming_root.rglob("*"):
            if path.is_file() and not path.is_symlink() and path not in expected_parts:
                issues.append(IntegrityIssue("orphan_part", str(path)))

    return IntegrityReport(
        checked_photos=len(photos),
        checked_derivatives=checked_derivatives,
        issues=tuple(sorted(issues, key=lambda issue: (issue.code, issue.path))),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check photo files and database records without modifying them")
    parser.add_argument(
        "--verify-hashes",
        action="store_true",
        help="Read every original and compare its SHA-256 digest (slower)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_management_settings()
    if settings.photo_storage_root is None:
        raise SystemExit("PHOTO_STORAGE_ROOT is not configured")
    storage = PhotoStorage(settings)
    storage_status = storage.get_read_status()
    if not storage_status.available:
        raise SystemExit(f"Photo storage is unavailable: {storage_status.status}")

    engine = create_database_engine(settings)
    try:
        with Session(engine) as session:
            maintenance = MaintenanceService(session, storage)
            run = maintenance.start_run(MaintenanceJobType.PHOTO_INTEGRITY)
            try:
                report = check_photo_integrity(
                    session,
                    storage,
                    settings.photo_storage_root,
                    settings.photo_derivative_root,
                    verify_hashes=args.verify_hashes,
                )
            except BaseException as error:
                maintenance.fail_run(run, error_code="photo_integrity_failed", error=error)
                raise
            maintenance.finish_run(
                run,
                MaintenanceRunStatus.SUCCEEDED if report.clean else MaintenanceRunStatus.WARNING,
                summary={
                    "checked_photos": report.checked_photos,
                    "checked_derivatives": report.checked_derivatives,
                    "issue_count": len(report.issues),
                    "verify_hashes": args.verify_hashes,
                    "issue_counts": {
                        code: sum(issue.code == code for issue in report.issues)
                        for code in sorted({issue.code for issue in report.issues})
                    },
                },
            )
    finally:
        engine.dispose()

    print(f"Checked {report.checked_photos} photo(s) and {report.checked_derivatives} derivative(s)")
    for issue in report.issues:
        photo = f" photo={issue.photo_id}" if issue.photo_id is not None else ""
        print(f"{issue.code}:{photo} path={issue.path}")
    if report.clean:
        print("No integrity issues found")
        return
    raise SystemExit(1)


if __name__ == "__main__":
    main()
