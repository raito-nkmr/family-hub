"""Generate missing HDD-backed WebP previews for still photos."""

import argparse
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_management_settings
from app.database.session import create_database_engine
from app.features.photos.models import Photo, PhotoDerivative, PhotoDerivativeKind
from app.features.photos.registration import build_sidecar_metadata
from app.features.photos.storage.facade import PhotoStorage, PhotoStorageError


@dataclass(frozen=True, slots=True)
class PreviewGenerationReport:
    checked_photos: int
    generated_previews: int
    skipped_previews: int
    failures: tuple[str, ...]


def generate_photo_previews(
    session: Session,
    storage: PhotoStorage,
    *,
    limit: int | None = None,
) -> PreviewGenerationReport:
    statement = select(Photo).where(Photo.content_type.like("image/%")).order_by(Photo.uploaded_at, Photo.id)
    if limit is not None:
        statement = statement.limit(limit)

    photos = list(session.scalars(statement).all())
    generated_count = 0
    skipped_count = 0
    failures: list[str] = []

    for photo in photos:
        destination = None
        derivative = photo.get_derivative(PhotoDerivativeKind.PREVIEW)
        storage_key = (
            derivative.storage_key if derivative is not None else f"previews/{photo.uploaded_at:%Y/%m}/{photo.id}.webp"
        )
        try:
            if derivative is not None:
                try:
                    storage.get_derivative_path(storage_key)
                except PhotoStorageError:
                    pass
                else:
                    skipped_count += 1
                    continue

            original_path = storage.get_original_path(photo.storage_key)
            staged = storage.stage_preview(original_path, storage_key)
            destination = storage.finalize_staged_derivative(staged)
            previous_metadata = build_sidecar_metadata(photo)
            if derivative is None:
                derivative = PhotoDerivative(
                    id=uuid4(),
                    photo_id=photo.id,
                    kind=PhotoDerivativeKind.PREVIEW,
                    storage_key=storage_key,
                    content_type=staged.content_type,
                    width=staged.width,
                    height=staged.height,
                    size_bytes=staged.size_bytes,
                    created_at=photo.uploaded_at,
                )
                photo.derivatives.append(derivative)
            else:
                derivative.content_type = staged.content_type
                derivative.width = staged.width
                derivative.height = staged.height
                derivative.size_bytes = staged.size_bytes

            storage.update_sidecar(build_sidecar_metadata(photo))
            try:
                session.commit()
            except SQLAlchemyError:
                session.rollback()
                try:
                    storage.update_sidecar(previous_metadata)
                except PhotoStorageError:
                    pass
                destination.unlink(missing_ok=True)
                raise
        except (OSError, PhotoStorageError, SQLAlchemyError) as error:
            session.rollback()
            if destination is not None:
                destination.unlink(missing_ok=True)
            failures.append(f"{photo.id}:{type(error).__name__}")
        else:
            generated_count += 1

    return PreviewGenerationReport(
        checked_photos=len(photos),
        generated_previews=generated_count,
        skipped_previews=skipped_count,
        failures=tuple(failures),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate missing HDD-backed WebP photo previews")
    parser.add_argument("--limit", type=int, choices=range(1, 10001), metavar="1-10000")
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
            report = generate_photo_previews(session, storage, limit=args.limit)
    finally:
        engine.dispose()

    print(
        f"Checked {report.checked_photos} photo(s), generated {report.generated_previews} preview(s), "
        f"skipped {report.skipped_previews} existing preview(s)"
    )
    for failure in report.failures:
        print(f"failure:{failure}")
    if report.failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
